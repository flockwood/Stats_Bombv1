# statsbomb_fetcher.py
"""Threaded StatsBomb data fetcher for fast performance"""

import requests
import pandas as pd
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import concurrent.futures
from threading import Lock
import time
import os
import pickle


class StatsBombFetcher:
    """Fetches and processes data from StatsBomb's open data repository with threading"""
    
    def __init__(self, max_workers: int = 10, cache_dir: str = "statsbomb_cache"):
        self.base_url = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
        self._memory_cache = {}
        self._cache_lock = Lock()
        self.max_workers = max_workers
        self.cache_dir = cache_dir
        
        # Create cache directory if it doesn't exist
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
    
    def _get_cache_path(self, cache_key: str) -> str:
        """Get file path for cache"""
        return os.path.join(self.cache_dir, f"{cache_key}.pkl")
    
    def _load_from_disk_cache(self, cache_key: str):
        """Load data from disk cache if available"""
        cache_path = self._get_cache_path(cache_key)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
            except:
                pass
        return None
    
    def _save_to_disk_cache(self, cache_key: str, data):
        """Save data to disk cache"""
        cache_path = self._get_cache_path(cache_key)
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
        except:
            pass
    
    def get_competitions(self) -> pd.DataFrame:
        """Get all available competitions"""
        cache_key = 'competitions'
        
        # Check memory cache
        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key]
        
        # Check disk cache
        cached_data = self._load_from_disk_cache(cache_key)
        if cached_data is not None:
            self._memory_cache[cache_key] = cached_data
            return cached_data
        
        # Fetch from API
        response = requests.get(f"{self.base_url}/competitions.json")
        response.raise_for_status()
        
        competitions = pd.DataFrame(response.json())
        
        # Cache the data
        self._memory_cache[cache_key] = competitions
        self._save_to_disk_cache(cache_key, competitions)
        
        return competitions
    
    def get_matches(self, competition_id: int, season_id: int) -> pd.DataFrame:
        """Get all matches for a specific competition and season"""
        cache_key = f"matches_{competition_id}_{season_id}"
        
        # Check memory cache
        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key]
        
        # Check disk cache
        cached_data = self._load_from_disk_cache(cache_key)
        if cached_data is not None:
            self._memory_cache[cache_key] = cached_data
            return cached_data
        
        # Fetch from API
        url = f"{self.base_url}/matches/{competition_id}/{season_id}.json"
        response = requests.get(url)
        response.raise_for_status()
        
        matches = pd.DataFrame(response.json())
        
        # Cache the data
        self._memory_cache[cache_key] = matches
        self._save_to_disk_cache(cache_key, matches)
        
        return matches
    
    def get_match_events(self, match_id: int) -> pd.DataFrame:
        """Get all events from a specific match"""
        cache_key = f"events_{match_id}"
        
        # Check memory cache
        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key]
        
        # Check disk cache
        cached_data = self._load_from_disk_cache(cache_key)
        if cached_data is not None:
            self._memory_cache[cache_key] = cached_data
            return cached_data
        
        # Fetch from API
        url = f"{self.base_url}/events/{match_id}.json"
        response = requests.get(url)
        response.raise_for_status()
        
        events = pd.DataFrame(response.json())
        
        # Cache the data
        self._memory_cache[cache_key] = events
        self._save_to_disk_cache(cache_key, events)
        
        return events
    
    def _fetch_single_match_events(self, match_id: int) -> Tuple[int, pd.DataFrame]:
        """Fetch events for a single match (used by thread pool)"""
        try:
            events = self.get_match_events(match_id)
            return match_id, events
        except Exception as e:
            print(f"\nError fetching match {match_id}: {e}")
            return match_id, pd.DataFrame()
    
    def _fetch_single_match_data(self, match_info: dict) -> Optional[pd.DataFrame]:
        """Fetch and process a single match's player stats"""
        try:
            match_id = match_info['match_id']
            events = self.get_match_events(match_id)
            
            if events.empty:
                return None
            
            # Get lineups
            lineups = self.get_lineups(match_id)
            
            # Calculate player stats
            player_stats = self._calculate_player_match_stats(events, lineups, match_info)
            return player_stats
            
        except Exception as e:
            print(f"\nError processing match {match_info['match_id']}: {e}")
            return None
    
    def get_lineups(self, match_id: int) -> Dict:
        """Get lineups for a specific match"""
        cache_key = f"lineups_{match_id}"
        
        # Check memory cache
        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key]
        
        # Check disk cache
        cached_data = self._load_from_disk_cache(cache_key)
        if cached_data is not None:
            self._memory_cache[cache_key] = cached_data
            return cached_data
        
        # Fetch from API
        url = f"{self.base_url}/lineups/{match_id}.json"
        try:
            response = requests.get(url)
            response.raise_for_status()
            lineups = response.json()
            
            # Cache the data
            self._memory_cache[cache_key] = lineups
            self._save_to_disk_cache(cache_key, lineups)
            
            return lineups
        except:
            return []
    
    def _calculate_player_match_stats(self, events: pd.DataFrame, lineups: List, match_info: dict) -> pd.DataFrame:
        """Calculate player statistics from match events"""
        player_stats = {}
        
        # Initialize stats for all players in lineups
        for team in lineups:
            for player in team.get('lineup', []):
                player_id = player['player_id']
                player_stats[player_id] = {
                    'player_name': player['player_name'],
                    'team_name': team['team_name'],
                    'position': player['positions'][0]['position'] if player['positions'] else 'Unknown',
                    'match_id': match_info['match_id'],
                    'match_date': match_info['match_date'],
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
                # Player not in starting lineup (might be a sub)
                player_stats[player_id] = {
                    'player_name': event['player']['name'],
                    'team_name': event.get('team', {}).get('name', 'Unknown'),
                    'position': 'Unknown',
                    'match_id': match_info['match_id'],
                    'match_date': match_info['match_date'],
                    'minutes_played': 45,  # Assume sub
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
    
    def get_player_match_stats(self, match_id: int) -> pd.DataFrame:
        """Get player statistics for a specific match"""
        events = self.get_match_events(match_id)
        lineups = self.get_lineups(match_id)
        
        # Get match info (simplified)
        match_info = {'match_id': match_id, 'match_date': ''}
        
        return self._calculate_player_match_stats(events, lineups, match_info)
    
    def get_player_season_stats(self, competition_id: int, season_id: int, 
                               player_name: str = None) -> pd.DataFrame:
        """Aggregate player statistics across a season using parallel processing"""
        start_time = time.time()
        
        matches = self.get_matches(competition_id, season_id)
        total_matches = len(matches)
        
        print(f"Processing {total_matches} matches using {self.max_workers} threads...")
        
        all_player_stats = []
        
        # Use ThreadPoolExecutor for parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all match processing tasks
            future_to_match = {
                executor.submit(self._fetch_single_match_data, match.to_dict()): idx 
                for idx, match in matches.iterrows()
            }
            
            # Process completed tasks with progress bar
            completed = 0
            for future in concurrent.futures.as_completed(future_to_match):
                result = future.result()
                if result is not None:
                    all_player_stats.append(result)
                
                completed += 1
                print(f"Progress: {completed}/{total_matches} matches processed", end='\r')
        
        print(f"\nCompleted in {time.time() - start_time:.2f} seconds")
        
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
        
        # Handle division by zero
        aggregated = aggregated.fillna(0)
        aggregated = aggregated.replace([float('inf'), -float('inf')], 0)
        
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
