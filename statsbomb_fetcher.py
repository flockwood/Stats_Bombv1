# statsbomb_fetcher.py
"""Module for fetching and processing StatsBomb open data"""

import requests
import pandas as pd
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class StatsBombFetcher:
    """Fetches and processes data from StatsBomb's open data repository"""
    
    def __init__(self):
        self.base_url = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
        self._cache = {}
        
    def get_competitions(self) -> pd.DataFrame:
        """Get all available competitions"""
        url = f"{self.base_url}/competitions.json"
        
        if 'competitions' in self._cache:
            return self._cache['competitions']
        
        response = requests.get(url)
        response.raise_for_status()
        
        competitions = pd.DataFrame(response.json())
        self._cache['competitions'] = competitions
        
        return competitions
    
    def get_matches(self, competition_id: int, season_id: int) -> pd.DataFrame:
        """Get all matches for a specific competition and season"""
        url = f"{self.base_url}/matches/{competition_id}/{season_id}.json"
        
        cache_key = f"matches_{competition_id}_{season_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        response = requests.get(url)
        response.raise_for_status()
        
        matches = pd.DataFrame(response.json())
        self._cache[cache_key] = matches
        
        return matches
    
    def get_match_events(self, match_id: int) -> pd.DataFrame:
        """Get all events from a specific match"""
        url = f"{self.base_url}/events/{match_id}.json"
        
        cache_key = f"events_{match_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        response = requests.get(url)
        response.raise_for_status()
        
        events = pd.DataFrame(response.json())
        self._cache[cache_key] = events
        
        return events
    
    def get_lineups(self, match_id: int) -> Dict:
        """Get lineups for a specific match"""
        url = f"{self.base_url}/lineups/{match_id}.json"
        
        response = requests.get(url)
        response.raise_for_status()
        
        return response.json()
    
    def get_player_match_stats(self, match_id: int) -> pd.DataFrame:
        """Calculate player statistics from match events"""
        events = self.get_match_events(match_id)
        lineups = self.get_lineups(match_id)
        
        player_stats = {}
        
        # Initialize stats for all players
        for team in lineups:
            for player in team['lineup']:
                player_id = player['player_id']
                player_stats[player_id] = {
                    'player_name': player['player_name'],
                    'team_name': team['team_name'],
                    'position': player['positions'][0]['position'] if player['positions'] else 'Unknown',
                    'minutes_played': 90,  # Default, will adjust for subs
                    'passes': 0,
                    'passes_completed': 0,
                    'shots': 0,
                    'shots_on_target': 0,
                    'goals': 0,
                    'assists': 0,
                    'key_passes': 0,
                    'dribbles': 0,
                    'dribbles_completed': 0,
                    'tackles': 0,
                    'interceptions': 0,
                    'clearances': 0,
                    'fouls': 0,
                    'cards_yellow': 0,
                    'cards_red': 0,
                    'touches': 0,
                    'xg': 0.0,
                    'xa': 0.0
                }
        
        # Process events
        for _, event in events.iterrows():
            if 'player' not in event or pd.isna(event['player']):
                continue
                
            player_id = event['player']['id']
            if player_id not in player_stats:
                continue
            
            event_type = event['type']['name']
            
            # Count different event types
            if event_type == 'Pass':
                player_stats[player_id]['passes'] += 1
                if event.get('pass', {}).get('outcome', {}).get('name') != 'Incomplete':
                    player_stats[player_id]['passes_completed'] += 1
                
                # Check for assists
                if event.get('pass', {}).get('goal_assist'):
                    player_stats[player_id]['assists'] += 1
                elif event.get('pass', {}).get('shot_assist'):
                    player_stats[player_id]['key_passes'] += 1
                    
            elif event_type == 'Shot':
                player_stats[player_id]['shots'] += 1
                if event.get('shot', {}).get('outcome', {}).get('name') == 'Goal':
                    player_stats[player_id]['goals'] += 1
                    player_stats[player_id]['shots_on_target'] += 1
                elif not event.get('shot', {}).get('outcome', {}).get('name') in ['Blocked', 'Off T', 'Wayward']:
                    player_stats[player_id]['shots_on_target'] += 1
                
                # Add xG if available
                if 'shot' in event and 'statsbomb_xg' in event['shot']:
                    player_stats[player_id]['xg'] += event['shot']['statsbomb_xg']
                    
            elif event_type == 'Dribble':
                player_stats[player_id]['dribbles'] += 1
                if event.get('dribble', {}).get('outcome', {}).get('name') == 'Complete':
                    player_stats[player_id]['dribbles_completed'] += 1
                    
            elif event_type in ['Tackle', 'Duel'] and event.get('duel', {}).get('type', {}).get('name') == 'Tackle':
                player_stats[player_id]['tackles'] += 1
                
            elif event_type == 'Interception':
                player_stats[player_id]['interceptions'] += 1
                
            elif event_type == 'Clearance':
                player_stats[player_id]['clearances'] += 1
                
            elif event_type == 'Foul Committed':
                player_stats[player_id]['fouls'] += 1
                
                # Check for cards
                if 'foul_committed' in event:
                    if event['foul_committed'].get('card', {}).get('name') == 'Yellow Card':
                        player_stats[player_id]['cards_yellow'] += 1
                    elif event['foul_committed'].get('card', {}).get('name') == 'Red Card':
                        player_stats[player_id]['cards_red'] += 1
            
            # Count all events as touches
            player_stats[player_id]['touches'] += 1
        
        return pd.DataFrame.from_dict(player_stats, orient='index')
    
    def get_player_season_stats(self, competition_id: int, season_id: int, 
                               player_name: str = None) -> pd.DataFrame:
        """Aggregate player statistics across a season"""
        matches = self.get_matches(competition_id, season_id)
        
        all_player_stats = []
        
        print(f"Processing {len(matches)} matches...")
        for idx, match in matches.iterrows():
            try:
                match_stats = self.get_player_match_stats(match['match_id'])
                match_stats['match_id'] = match['match_id']
                match_stats['match_date'] = match['match_date']
                match_stats['competition'] = match['competition']['competition_name']
                all_player_stats.append(match_stats)
            except Exception as e:
                print(f"Error processing match {match['match_id']}: {e}")
                continue
        
        if not all_player_stats:
            return pd.DataFrame()
        
        # Combine all match stats
        season_stats = pd.concat(all_player_stats)
        
        # Filter by player if specified
        if player_name:
            season_stats = season_stats[
                season_stats['player_name'].str.contains(player_name, case=False, na=False)
            ]
        
        # Aggregate stats
        aggregated = season_stats.groupby(['player_name', 'team_name', 'position']).agg({
            'match_id': 'count',  # Games played
            'minutes_played': 'sum',
            'goals': 'sum',
            'assists': 'sum',
            'shots': 'sum',
            'shots_on_target': 'sum',
            'passes': 'sum',
            'passes_completed': 'sum',
            'key_passes': 'sum',
            'dribbles': 'sum',
            'dribbles_completed': 'sum',
            'tackles': 'sum',
            'interceptions': 'sum',
            'clearances': 'sum',
            'fouls': 'sum',
            'cards_yellow': 'sum',
            'cards_red': 'sum',
            'touches': 'sum',
            'xg': 'sum',
            'xa': 'sum'
        }).rename(columns={'match_id': 'games_played'})
        
        # Calculate per 90 stats
        aggregated['goals_per_90'] = (aggregated['goals'] / aggregated['minutes_played']) * 90
        aggregated['assists_per_90'] = (aggregated['assists'] / aggregated['minutes_played']) * 90
        aggregated['shots_per_90'] = (aggregated['shots'] / aggregated['minutes_played']) * 90
        aggregated['key_passes_per_90'] = (aggregated['key_passes'] / aggregated['minutes_played']) * 90
        aggregated['tackles_per_90'] = (aggregated['tackles'] / aggregated['minutes_played']) * 90
        aggregated['pass_completion'] = (aggregated['passes_completed'] / aggregated['passes']) * 100
        aggregated['dribble_success'] = (aggregated['dribbles_completed'] / aggregated['dribbles']) * 100
        aggregated['shot_accuracy'] = (aggregated['shots_on_target'] / aggregated['shots']) * 100
        aggregated['xg_per_90'] = (aggregated['xg'] / aggregated['minutes_played']) * 90
        aggregated['xa_per_90'] = (aggregated['xa'] / aggregated['minutes_played']) * 90
        
        return aggregated.reset_index()
    
    def get_team_stats(self, competition_id: int, season_id: int) -> pd.DataFrame:
        """Get aggregated team statistics for a season"""
        matches = self.get_matches(competition_id, season_id)
        
        team_stats = {}
        
        for _, match in matches.iterrows():
            home_team = match['home_team']['home_team_name']
            away_team = match['away_team']['away_team_name']
            
            # Initialize teams if not seen
            for team in [home_team, away_team]:
                if team not in team_stats:
                    team_stats[team] = {
                        'games': 0,
                        'wins': 0,
                        'draws': 0,
                        'losses': 0,
                        'goals_for': 0,
                        'goals_against': 0,
                        'xg_for': 0,
                        'xg_against': 0
                    }
            
            # Update match results
            home_score = match['home_score']
            away_score = match['away_score']
            
            team_stats[home_team]['games'] += 1
            team_stats[away_team]['games'] += 1
            
            team_stats[home_team]['goals_for'] += home_score
            team_stats[home_team]['goals_against'] += away_score
            team_stats[away_team]['goals_for'] += away_score
            team_stats[away_team]['goals_against'] += home_score
            
            if home_score > away_score:
                team_stats[home_team]['wins'] += 1
                team_stats[away_team]['losses'] += 1
            elif home_score < away_score:
                team_stats[away_team]['wins'] += 1
                team_stats[home_team]['losses'] += 1
            else:
                team_stats[home_team]['draws'] += 1
                team_stats[away_team]['draws'] += 1
        
        df = pd.DataFrame.from_dict(team_stats, orient='index')
        df['points'] = df['wins'] * 3 + df['draws']
        df['goal_difference'] = df['goals_for'] - df['goals_against']
        
        return df.sort_values('points', ascending=False).reset_index().rename(columns={'index': 'team'})
    
    def get_player_heatmap_data(self, match_id: int, player_name: str) -> List[Dict]:
        """Get location data for player heatmap"""
        events = self.get_match_events(match_id)
        
        # Filter events by player
        player_events = events[
            events['player'].apply(lambda x: x.get('name', '') if isinstance(x, dict) else '') == player_name
        ]
        
        locations = []
        for _, event in player_events.iterrows():
            if 'location' in event and event['location'] is not None:
                locations.append({
                    'x': event['location'][0],
                    'y': event['location'][1],
                    'event_type': event['type']['name']
                })
        
        return locations
    
    def get_passing_network(self, match_id: int, team_name: str) -> Dict:
        """Generate passing network data for a team in a match"""
        events = self.get_match_events(match_id)
        lineups = self.get_lineups(match_id)
        
        # Get team lineup
        team_lineup = None
        for team in lineups:
            if team['team_name'] == team_name:
                team_lineup = team['lineup']
                break
        
        if not team_lineup:
            return {}
        
        # Create player position mapping
        player_positions = {}
        for player in team_lineup:
            player_positions[player['player_name']] = {
                'id': player['player_id'],
                'position': player['positions'][0]['position'] if player['positions'] else 'Unknown'
            }
        
        # Count passes between players
        pass_network = {}
        
        passes = events[events['type'].apply(lambda x: x['name']) == 'Pass']
        
        for _, pass_event in passes.iterrows():
            if 'player' not in pass_event or pd.isna(pass_event['player']):
                continue
            
            passer = pass_event['player']['name']
            
            # Check if pass has recipient
            if 'pass' in pass_event and 'recipient' in pass_event['pass']:
                recipient = pass_event['pass']['recipient']['name']
                
                # Only count if both players are from the team
                if passer in player_positions and recipient in player_positions:
                    key = f"{passer}->{recipient}"
                    pass_network[key] = pass_network.get(key, 0) + 1
        
        return {
            'players': player_positions,
            'passes': pass_network
        }


# Example usage functions
def analyze_premier_league_players():
    """Example: Analyze Premier League players from StatsBomb data"""
    fetcher = StatsBombFetcher()
    
    # Get competitions
    competitions = fetcher.get_competitions()
    
    # Find Premier League
    pl = competitions[
        (competitions['competition_name'] == 'Premier League') & 
        (competitions['season_name'] == '2003/2004')  # StatsBomb has this season
    ]
    
    if not pl.empty:
        comp_id = pl.iloc[0]['competition_id']
        season_id = pl.iloc[0]['season_id']
        
        # Get season stats
        season_stats = fetcher.get_player_season_stats(comp_id, season_id)
        
        # Find top scorers
        top_scorers = season_stats.nlargest(10, 'goals')[
            ['player_name', 'team_name', 'goals', 'assists', 'xg', 'games_played']
        ]
        
        print("Top Scorers - Premier League 2003/2004:")
        print(top_scorers)
        
        return season_stats
    
    return None


def analyze_world_cup_players():
    """Example: Analyze World Cup players"""
    fetcher = StatsBombFetcher()
    
    # Get competitions
    competitions = fetcher.get_competitions()
    
    # Find World Cup
    wc = competitions[
        competitions['competition_name'] == 'FIFA World Cup'
    ]
    
    print("Available World Cup seasons:")
    print(wc[['competition_name', 'season_name']])
    
    # Get latest World Cup
    if not wc.empty:
        latest_wc = wc.iloc[-1]
        comp_id = latest_wc['competition_id']
        season_id = latest_wc['season_id']
        
        # Get player stats
        player_stats = fetcher.get_player_season_stats(comp_id, season_id)
        
        # Top performers by xG
        top_xg = player_stats.nlargest(10, 'xg')[
            ['player_name', 'team_name', 'goals', 'xg', 'shots', 'games_played']
        ]
        
        print(f"\nTop xG - {latest_wc['season_name']} World Cup:")
        print(top_xg)
        
        return player_stats
