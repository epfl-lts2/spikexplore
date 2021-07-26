import time
import logging
from TwitterAPI import TwitterAPI
from twython import Twython
from twython import TwythonError, TwythonRateLimitError, TwythonAuthError
import pandas as pd
from datetime import datetime, timedelta
from spikexplore.NodeInfo import NodeInfo
from spikexplore.graph import add_node_attributes, add_edges_attributes

logger = logging.getLogger(__name__)


class TwitterCredentials:
    def __init__(self, app_key, access_token, consumer_key=None, consumer_secret=None):
        self.app_key = app_key
        self.access_token = access_token
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret


class TweetsGetterV1:
    def __init__(self, credentials, config):
        # Instantiate an object
        self.app_key = credentials.app_key
        self.access_token = credentials.access_token
        self.config = config
        self.twitter_handle = Twython(self.app_key, access_token=self.access_token)
        pass

    def _filter_old_tweets(self, tweets):
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
            user_tweets_filt = self._filter_old_tweets(user_tweets_raw)
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
                logger.warning('Unauthorized access to user {}. Skipping.'.format(username))
                return {}, {}
            else:
                logger.error('Cannot access to twitter API, authentification error. {}'.format(e_auth.error_code))
                raise
        except TwythonRateLimitError as e_lim:
            logger.warning('API rate limit reached')
            logger.warning(e_lim)
            remainder = float(self.twitter_handle.get_lastfunction_header(header='x-rate-limit-reset')) - time.time()
            logger.warning('Retry after {} seconds.'.format(remainder))
            time.sleep(remainder + 1)
            del self.twitter_handle
            self.twitter_handle = Twython(self.app_key, access_token=self.access_token)  # seems you need this
            return {}, {}  # best way to handle it ?
        except TwythonError as e:
            logger.error('Twitter API returned error {} for user {}.'.format(e.error_code, username))
            return {}, {}

    def reshape_node_data(self, node_df):
        # user name user_details mentions hashtags retweet_count favorite_count
        # created_at account_creation account_followers account_following account_statuses account_favourites
        # account_verified account_default_profile account_default_profile_image spikyball_hop
        node_df = node_df[
            ['user', 'name', 'user_details', 'spikyball_hop', 'account_creation', 'account_default_profile',
             'account_default_profile_image', 'account_favourites', 'account_followers', 'account_following',
             'account_statuses', 'account_verified']]
        node_df = node_df.reset_index().groupby('user').max().rename(columns={'index': 'max_tweet_id'})
        return node_df


class TweetsGetterV2:
    def __init__(self, credentials, config):
        self.twitter_handle = TwitterAPI(credentials.consumer_key, credentials.consumer_secret,
                                         api_version='2', auth_type='oAuth2')
        self.config = config
        self.start_time = None
        if config.max_day_old:
            days_limit = datetime.now() - timedelta(days=config.max_day_old)
            #  date format: 2010-11-06T00:00:00Z
            self.start_time = days_limit.strftime('%Y-%m-%dT%H:%M:%SZ')
        self.user_cache = {}

    def _safe_twitter_request(self, request_str, params):
        res = self.twitter_handle.request(request_str, params)
        while res.status_code == 429:  # rate limit reached
            logger.warning('API rate limit reached')
            remainder = float(res.header['x-rate-limit-reset']) - time.time()
            logger.warning('Retry after {} seconds.'.format(remainder))
            time.sleep(remainder + 1)
            res = self.twitter_handle.request(request_str, params)

        if res.status_code != 200:
            logger.warning('API returned with code {}'.format(res.status_code))

        return res

    def _get_user_info(self, username):
        if username not in self.user_cache:
            params = {'user.fields': 'created_at,verified,description,public_metrics,protected,profile_image_url'}
            res = dict(self._safe_twitter_request('users/by/username/:{}'.format(username), params).json())

            if 'errors' in res:
                self.user_cache[username] = None
                for e in res['errors']:
                    logger.error(e['detail'])
            else:
                self.user_cache[username] = res['data']
        return self.user_cache[username]

    def _get_user_tweets(self, username, num_tweets, next_token):
        assert(num_tweets <= 100 and num_tweets > 0)
        params = {'max_results': num_tweets, 'expansions': 'author_id,entities.mentions.username',
                  'tweet.fields': 'entities,created_at,public_metrics,lang'}
        if self.start_time:
            params['start_time'] = self.start_time

        if next_token:
            params['pagination_token'] = next_token

        user_info = self._get_user_info(username)
        if not user_info:  # not found
            return {}, {}, None
        if user_info['protected']:
            logger.info('Skipping user {} - protected account'.format(username))
            return {}, {}, None

        tweets_raw = dict(self._safe_twitter_request('users/:{}/tweets'.format(user_info['id']), params).json())

        if 'errors' in tweets_raw:
            for e in tweets_raw['errors']:
                logger.error(e['detail'])

        if 'data' not in tweets_raw:
            logger.warning('Empty results for {}'.format(username))
            return {}, {}, None

        user_tweets = {int(x['id']): x for x in tweets_raw['data']}
        tweets_metadata = \
            dict(map(lambda x: (x[0], {'user': user_info['username'],
                                       'name': user_info['name'],
                                       'user_details': user_info['description'],
                                       'mentions': list(
                                           map(lambda y: y['username'], x[1].get('entities', {}).get('mentions', {}))),
                                       'hashtags': list(
                                           map(lambda y: y['tag'], x[1].get('entities', {}).get('hashtags', {}))),
                                       'retweet_count': x[1]['public_metrics']['retweet_count'],
                                       'favorite_count': x[1]['public_metrics']['like_count'],
                                       'created_at': x[1]['created_at'],
                                       'account_creation': user_info['created_at'],
                                       'account_followers': user_info['public_metrics']['followers_count'],
                                       'account_following': user_info['public_metrics']['following_count'],
                                       'account_statuses': user_info['public_metrics']['tweet_count'],
                                       'account_verified': user_info['verified']}),
                     user_tweets.items()))

        return user_tweets, tweets_metadata, tweets_raw['meta'].get('next_token', None)

    def get_user_tweets(self, username):
        remaining_number_of_tweets = self.config.max_tweets_per_user
        next_token = None
        user_tweets_acc = {}
        tweets_metadata_acc = {}
        while remaining_number_of_tweets > 0:
            number_of_tweets = 100 if remaining_number_of_tweets > 100 else remaining_number_of_tweets
            remaining_number_of_tweets -= number_of_tweets
            user_tweets, tweets_metadata, next_token = self._get_user_tweets(username, number_of_tweets, next_token)
            user_tweets_acc.update(user_tweets)
            tweets_metadata_acc.update(tweets_metadata)
            if not next_token:
                break
        return user_tweets_acc, tweets_metadata_acc


    def reshape_node_data(self, node_df):
        node_df = node_df[
            ['user', 'name', 'user_details', 'spikyball_hop', 'account_creation',
             'account_followers', 'account_following',
             'account_statuses', 'account_verified']]
        node_df = node_df.reset_index().groupby('user').max().rename(columns={'index': 'max_tweet_id'})
        return node_df


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
        if config.api_version == 1:
            self.tweets_getter = TweetsGetterV1(credentials, config)
        elif config.api_version == 2:
            self.tweets_getter = TweetsGetterV2(credentials, config)
        else:
            raise ValueError("Invalid api version")
        self.config = config

    def get_node_info(self):
        return self.TwitterNodeInfo()

    def get_neighbors(self, user):
        if not isinstance(user, str):
            return self.TwitterNodeInfo(), pd.DataFrame()
        tweets_dic, tweets_meta = self.tweets_getter.get_user_tweets(user)
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

    def add_graph_attributes(self, g, nodes_df, edges_df, nodes_info):
        g = add_edges_attributes(g, edges_df, drop_cols=['tweet_id', 'degree_target', 'degree_source'])
        g = add_node_attributes(g, self.tweets_getter.reshape_node_data(nodes_df), attr_dic=nodes_info.user_hashtags,
                                attr_name='all_hashtags')
        return g
