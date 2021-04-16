import time
import logging
from twython import Twython
from twython import TwythonError, TwythonRateLimitError, TwythonAuthError
import pandas as pd
from datetime import datetime, timedelta
from spikexplore.NodeInfo import NodeInfo
from spikexplore.graph import add_node_attributes, add_edges_attributes


class TwitterCredentials:
    def __init__(self, app_key, access_token):
        self.app_key = app_key
        self.access_token = access_token


class TwitterNetwork:
    class TwitterNodeInfo(NodeInfo):
        def __init__(self, user_hashtags={}, user_tweets={}, tweets_meta=pd.DataFrame()):
            self.user_hashtags = user_hashtags
            self.user_tweets = user_tweets
            self.tweets_meta = tweets_meta

        def update(self, new_info):
            self.user_hashtags.update(new_info.user_hashtags)
            self.user_tweets.update(new_info.user_tweets)

        def get_nodes(self):
            return self.tweets_meta

    def __init__(self, credentials, config):
        # Instantiate an object
        self.app_key = credentials.app_key
        self.access_token = credentials.access_token
        self.twitter_handle = Twython(self.app_key, access_token=self.access_token)
        self.config = config

    def get_node_info(self):
        return self.TwitterNodeInfo()

    def get_neighbors(self, user):
        if not isinstance(user, str):
            return self.TwitterNodeInfo(), pd.DataFrame()
        tweets_dic, tweets_meta = self.get_user_tweets(user)
        edges_df, node_info = self.edges_nodes_from_user(tweets_meta, tweets_dic)

        # replace user and mentions by source and target
        if not edges_df.empty:
            edges_df.index.names = ['source', 'target']
            edges_df.reset_index(level=['source', 'target'], inplace=True)

        return node_info, edges_df

    def filter(self, node_info, edges_df):
        # filter edges according to node properties
        # filter according to edges properties
        edges_df = self.filter_edges(edges_df)
        return node_info, edges_df

    def filter_edges(self, edges_df):
        # filter edges according to their properties
        if edges_df.empty:
            return edges_df
        return edges_df[edges_df['weight'] >= self.config.min_mentions]

    def neighbors_list(self, edges_df):
        if edges_df.empty:
            return edges_df
        users_connected = edges_df['target'].tolist()
        return users_connected

    def neighbors_with_weights(self, edges_df):
        user_list = self.neighbors_list(edges_df)
        return dict.fromkeys(user_list, 1)

    ###############################################################
    # Functions for extracting tweet info from the twitter API
    ###############################################################

    def filter_old_tweets(self, tweets):
        max_day_old = self.config.max_day_old
        if not max_day_old:
            return tweets

        days_limit = datetime.now() - timedelta(days=max_day_old)
        tweets_filt = filter(lambda t: datetime.strptime(t['created_at'], '%a %b %d %H:%M:%S +0000 %Y') >= days_limit,
                             tweets)
        return list(tweets_filt)

    def get_user_tweets(self, username):
        # Collect tweets from a username

        count = self.config.max_tweets_per_user

        # Test if ok
        try:
            user_tweets_raw = self.twitter_handle.get_user_timeline(screen_name=username,
                                                                    count=count, include_rts=True,
                                                                    tweet_mode='extended', exclude_replies=False)
            # remove old tweets
            user_tweets_filt = self.filter_old_tweets(user_tweets_raw)
            # make a dictionary
            user_tweets = {x['id']: x for x in user_tweets_filt}
            tweets_metadata = \
                map(lambda x: (x[0], {'user': x[1]['user']['screen_name'],
                                      'name': x[1]['user']['name'],
                                      'user_details': x[1]['user']['description'],
                                      'mentions': list(
                                          map(lambda y: y['screen_name'], x[1]['entities']['user_mentions'])),
                                      'hashtags': list(map(lambda y: y['text'], x[1]['entities']['hashtags'])),
                                      'retweet_count': x[1]['retweet_count'],
                                      'favorite_count': x[1]['favorite_count'], 'created_at': x[1]['created_at'],
                                      'account_creation': x[1]['user']['created_at'],
                                      'account_followers': x[1]['user']['followers_count'],
                                      'account_following': x[1]['user']['friends_count'],
                                      'account_statuses': x[1]['user']['statuses_count'],
                                      'account_favourites': x[1]['user']['favourites_count'],
                                      'account_verified': x[1]['user']['verified'],
                                      'account_default_profile': x[1]['user']['default_profile'],
                                      'account_default_profile_image': x[1]['user']['default_profile_image']}),
                    user_tweets.items())
            return user_tweets, dict(tweets_metadata)
        except TwythonAuthError as e_auth:
            if e_auth.error_code == 401:
                logging.warning('Unauthorized access to user {}. Skipping.'.format(username))
                return {}, {}
            else:
                logging.error('Cannot access to twitter API, authentification error. {}'.format(e_auth.error_code))
                raise
        except TwythonRateLimitError as e_lim:
            logging.warning('API rate limit reached')
            logging.warning(e_lim)
            remainder = float(self.twitter_handle.get_lastfunction_header(header='x-rate-limit-reset')) - time.time()
            logging.warning('Retry after {} seconds.'.format(remainder))
            time.sleep(remainder + 1)
            del self.twitter_handle
            self.twitter_handle = Twython(self.consumer_key, self.consumer_secret)  # seems you need this
            return {}, {}  # best way to handle it ?
        except TwythonError as e:
            logging.error('Twitter API returned error {} for user {}.'.format(e.error_code, username))
            return {}, {}

    def edges_nodes_from_user(self, tweets_meta, tweets_dic):
        # Make an edge and node property dataframes
        edges_df = self.get_edges(tweets_meta)
        user_info = self.get_nodes_properties(tweets_meta, tweets_dic)
        return edges_df, user_info

    def get_edges(self, tweets_meta):
        if not tweets_meta:
            return pd.DataFrame()
        # Create the user -> mention table with their properties fom the list of tweets of a user
        meta_df = pd.DataFrame.from_dict(tweets_meta, orient='index').explode('mentions').dropna()
        # Some bots to be removed from the collection
        users_to_remove = self.config.users_to_remove

        filtered_meta_df = meta_df[~meta_df['mentions'].isin(users_to_remove) &
                                   ~meta_df['mentions'].isin(meta_df['user'])]

        # group by mentions and keep list of tweets for each mention
        tmp = filtered_meta_df.groupby(['user', 'mentions']).apply(lambda x: (x.index.tolist(), len(x.index)))
        if tmp.empty:
            return tmp
        edge_df = pd.DataFrame(tmp.tolist(), index=tmp.index) \
            .rename(columns={0: 'tweet_id', 1: 'weight'})
        return edge_df

    def get_nodes_properties(self, tweets_meta, tweets_dic):
        if not tweets_meta:
            return self.TwitterNodeInfo({}, {}, pd.DataFrame())
        nb_popular_tweets = self.config.nb_popular_tweets
        # global properties
        meta_df = pd.DataFrame.from_dict(tweets_meta, orient='index') \
            .sort_values('retweet_count', ascending=False)
        # hashtags statistics
        ht_df = meta_df.explode('hashtags').dropna()
        htgb = ht_df.groupby(['hashtags']).size()
        user_hashtags = pd.DataFrame(htgb).rename(columns={0: 'count'}) \
            .sort_values('count', ascending=False).to_dict()
        user_name = meta_df['user'].iloc[0]
        tweets_meta_kept = meta_df.head(nb_popular_tweets)
        tweets_kept = {k: tweets_dic[k] for k in tweets_meta_kept.index.to_list()}
        # Get most popular tweets of user
        return self.TwitterNodeInfo({user_name: user_hashtags['count']}, tweets_kept, tweets_meta_kept)

    #####################################################
    ## Utils functions for the graph
    #####################################################

    def reshape_node_data(self, node_df):

        node_df = node_df[
            ['user', 'name', 'user_details', 'spikyball_hop', 'account_creation', 'account_default_profile',
             'account_default_profile_image', 'account_favourites', 'account_followers', 'account_following',
             'account_statuses', 'account_verified']]
        node_df = node_df.reset_index().groupby('user').max().rename(columns={'index': 'max_tweet_id'})
        return node_df

    def add_graph_attributes(self, g, nodes_df, edges_df, nodes_info):
        g = add_edges_attributes(g, edges_df, drop_cols=['tweet_id', 'degree_target', 'degree_source'])
        g = add_node_attributes(g, self.reshape_node_data(nodes_df), attr_dic=nodes_info.user_hashtags,
                                attr_name='all_hashtags')
        return g
