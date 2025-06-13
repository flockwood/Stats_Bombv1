# statsbomb_analyzer.py
"""Enhanced analyzer using StatsBomb detailed event data"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from statsbomb_fetcher import StatsBombFetcher
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.patches import Arc


class StatsBombAnalyzer:
    """Analyzes player and team performance using StatsBomb event data"""
    
    def __init__(self):
        self.fetcher = StatsBombFetcher(max_workers=10)  # Use threading
        
    def analyze_player_performance(self, player_name: str, 
                                 competition_name: str = None,
                                 season_name: str = None) -> Dict:
        """Comprehensive player analysis using StatsBomb data"""
        competitions = self.fetcher.get_competitions()
        
        # Filter competitions if specified
        if competition_name:
            competitions = competitions[competitions['competition_name'] == competition_name]
        if season_name:
            competitions = competitions[competitions['season_name'] == season_name]
        
        all_stats = []
        
        for _, comp in competitions.iterrows():
            try:
                stats = self.fetcher.get_player_season_stats(
                    comp['competition_id'], 
                    comp['season_id'],
                    player_name
                )
                if not stats.empty:
                    stats['competition'] = comp['competition_name']
                    stats['season'] = comp['season_name']
                    all_stats.append(stats)
            except:
                continue
        
        if not all_stats:
            return {"error": f"No data found for player {player_name}"}
        
        player_data = pd.concat(all_stats)
        
        # Aggregate across all competitions
        career_stats = player_data.groupby('player_name').agg({
            'games_played': 'sum',
            'minutes_played': 'sum',
            'goals': 'sum',
            'assists': 'sum',
            'xg': 'sum',
            'xa': 'sum',
            'shots': 'sum',
            'shots_on_target': 'sum',
            'passes': 'sum',
            'passes_completed': 'sum',
            'key_passes': 'sum',
            'tackles': 'sum',
            'interceptions': 'sum'
        }).iloc[0]
        
        # Calculate advanced metrics
        analysis = {
            'player_name': player_name,
            'career_stats': career_stats.to_dict(),
            'per_90_stats': {
                'goals_per_90': (career_stats['goals'] / career_stats['minutes_played']) * 90,
                'assists_per_90': (career_stats['assists'] / career_stats['minutes_played']) * 90,
                'xg_per_90': (career_stats['xg'] / career_stats['minutes_played']) * 90,
                'xa_per_90': (career_stats['xa'] / career_stats['minutes_played']) * 90,
                'shots_per_90': (career_stats['shots'] / career_stats['minutes_played']) * 90,
                'key_passes_per_90': (career_stats['key_passes'] / career_stats['minutes_played']) * 90,
                'tackles_per_90': (career_stats['tackles'] / career_stats['minutes_played']) * 90
            },
            'efficiency_metrics': {
                'goals_per_shot': career_stats['goals'] / career_stats['shots'] if career_stats['shots'] > 0 else 0,
                'shot_accuracy': career_stats['shots_on_target'] / career_stats['shots'] * 100 if career_stats['shots'] > 0 else 0,
                'pass_completion': career_stats['passes_completed'] / career_stats['passes'] * 100 if career_stats['passes'] > 0 else 0,
                'xg_overperformance': career_stats['goals'] - career_stats['xg'],
                'xa_overperformance': career_stats['assists'] - career_stats['xa']
            },
            'by_competition': player_data.to_dict('records')
        }
        
        return analysis
    
    def compare_players(self, player_names: List[str], 
                       metrics: List[str] = None) -> pd.DataFrame:
        """Compare multiple players across specified metrics"""
        if metrics is None:
            metrics = ['goals_per_90', 'assists_per_90', 'xg_per_90', 'xa_per_90', 
                      'shots_per_90', 'key_passes_per_90', 'tackles_per_90']
        
        comparison_data = []
        
        for player in player_names:
            analysis = self.analyze_player_performance(player)
            if 'error' not in analysis:
                player_metrics = {'player_name': player}
                player_metrics.update(analysis['per_90_stats'])
                player_metrics.update(analysis['efficiency_metrics'])
                comparison_data.append(player_metrics)
        
        comparison_df = pd.DataFrame(comparison_data)
        
        # Select only requested metrics
        available_metrics = [m for m in metrics if m in comparison_df.columns]
        return comparison_df[['player_name'] + available_metrics]
    
    def find_similar_players_statsbomb(self, target_player: str, 
                                      position_filter: str = None,
                                      top_n: int = 10) -> pd.DataFrame:
        """Find similar players based on StatsBomb playing style metrics"""
        # Get all available players from a recent competition
        competitions = self.fetcher.get_competitions()
        
        # Use a competition with many players (e.g., Premier League)
        pl = competitions[competitions['competition_name'] == 'Premier League'].iloc[-1]
        
        all_players = self.fetcher.get_player_season_stats(
            pl['competition_id'], 
            pl['season_id']
        )
        
        if all_players.empty:
            return pd.DataFrame()
        
        # Filter by position if specified
        if position_filter:
            all_players = all_players[all_players['position'].str.contains(position_filter, case=False)]
        
        # Get target player stats
        target_stats = all_players[all_players['player_name'] == target_player]
        if target_stats.empty:
            return pd.DataFrame()
        
        target_stats = target_stats.iloc[0]
        
        # Define similarity metrics based on position
        if 'Forward' in str(target_stats['position']):
            similarity_metrics = ['goals_per_90', 'xg_per_90', 'shots_per_90', 'touches']
        elif 'Midfield' in str(target_stats['position']):
            similarity_metrics = ['assists_per_90', 'xa_per_90', 'key_passes_per_90', 'pass_completion']
        elif 'Back' in str(target_stats['position']):
            similarity_metrics = ['tackles_per_90', 'interceptions', 'clearances', 'pass_completion']
        else:
            similarity_metrics = ['goals_per_90', 'assists_per_90', 'xg_per_90', 'xa_per_90']
        
        # Calculate similarity scores
        all_players['similarity_score'] = 0
        
        for metric in similarity_metrics:
            if metric in all_players.columns:
                # Normalize metric
                metric_std = all_players[metric].std()
                if metric_std > 0:
                    all_players['similarity_score'] += (
                        (all_players[metric] - target_stats[metric]).abs() / metric_std
                    )
        
        # Remove target player and sort by similarity
        similar = all_players[all_players['player_name'] != target_player].copy()
        similar = similar.sort_values('similarity_score').head(top_n)
        
        return similar[['player_name', 'team_name', 'position', 'games_played'] + 
                      similarity_metrics + ['similarity_score']]
    
    def visualize_player_radar(self, player_names: List[str]):
        """Create radar chart comparing players using StatsBomb metrics"""
        metrics = ['goals_per_90', 'assists_per_90', 'xg_per_90', 
                  'xa_per_90', 'shots_per_90', 'key_passes_per_90']
        
        comparison = self.compare_players(player_names, metrics)
        
        if comparison.empty:
            print("No data available for comparison")
            return
        
        # Number of variables
        num_vars = len(metrics)
        
        # Compute angle for each axis
        angles = [n / float(num_vars) * 2 * np.pi for n in range(num_vars)]
        angles += angles[:1]
        
        # Initialize the plot
        fig, ax = plt.subplots(figsize=(10, 8), subplot_kw=dict(projection='polar'))
        
        # Plot each player
        colors = ['red', 'blue', 'green', 'orange', 'purple']
        
        for idx, (_, player) in enumerate(comparison.iterrows()):
            # Normalize values to 0-100 scale
            values = []
            for metric in metrics:
                max_val = comparison[metric].max()
                if max_val > 0:
                    values.append((player[metric] / max_val) * 100)
                else:
                    values.append(0)
            values += values[:1]
            
            # Plot
            ax.plot(angles, values, 'o-', linewidth=2, 
                   label=player['player_name'], 
                   color=colors[idx % len(colors)])
            ax.fill(angles, values, alpha=0.25, 
                   color=colors[idx % len(colors)])
        
        # Fix axis to go in the right order and start at 12 o'clock
        ax.set_theta_offset(np.pi / 2)
        ax.set_theta_direction(-1)
        
        # Draw axis lines for each angle and label
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels([m.replace('_', ' ').title() for m in metrics])
        
        # Set y-axis limits and labels
        ax.set_ylim(0, 100)
        ax.set_yticks([20, 40, 60, 80, 100])
        ax.set_yticklabels(['20', '40', '60', '80', '100'])
        
        # Add legend and title
        plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
        plt.title('Player Comparison - StatsBomb Metrics', size=16, y=1.08)
        
        plt.tight_layout()
        plt.show()
    
    def visualize_pitch_heatmap(self, match_id: int, player_name: str):
        """Visualize player movement heatmap on pitch"""
        locations = self.fetcher.get_player_heatmap_data(match_id, player_name)
        
        if not locations:
            print(f"No location data found for {player_name}")
            return
        
        # Create pitch
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Pitch dimensions (StatsBomb uses 120x80)
        pitch_length = 120
        pitch_width = 80
        
        # Draw pitch
        plt.plot([0, 0, pitch_length, pitch_length, 0], 
                [0, pitch_width, pitch_width, 0, 0], 'black')
        plt.plot([pitch_length/2, pitch_length/2], [0, pitch_width], 'black')
        
        # Extract x and y coordinates
        x_coords = [loc['x'] for loc in locations]
        y_coords = [loc['y'] for loc in locations]
        
        # Create heatmap
        heatmap, xedges, yedges = np.histogram2d(x_coords, y_coords, bins=25)
        extent = [xedges[0], xedges[-1], yedges[0], yedges[-1]]
        
        plt.imshow(heatmap.T, origin='lower', extent=extent, cmap='hot', alpha=0.6)
        
        # Add pitch features
        center_circle = plt.Circle((pitch_length/2, pitch_width/2), 9.15, 
                                 color='black', fill=False)
        ax.add_patch(center_circle)
        
        # Add title
        plt.title(f'{player_name} - Touch Heatmap', fontsize=16)
        plt.xlabel('Pitch Length')
        plt.ylabel('Pitch Width')
        
        plt.tight_layout()
        plt.show()
    
    def visualize_passing_network(self, match_id: int, team_name: str):
        """Visualize team passing network"""
        network_data = self.fetcher.get_passing_network(match_id, team_name)
        
        if not network_data:
            print(f"No passing data found for {team_name}")
            return
        
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Draw pitch
        pitch_length = 120
        pitch_width = 80
        plt.plot([0, 0, pitch_length, pitch_length, 0], 
                [0, pitch_width, pitch_width, 0, 0], 'black')
        
        # Position players on pitch (simplified positioning)
        positions = {
            'Goalkeeper': (10, 40),
            'Center Back': (25, 40),
            'Right Back': (25, 60),
            'Left Back': (25, 20),
            'Central Midfield': (50, 40),
            'Right Midfield': (50, 60),
            'Left Midfield': (50, 20),
            'Center Forward': (90, 40),
            'Right Wing': (80, 65),
            'Left Wing': (80, 15)
        }
        
        # Plot players
        player_positions = {}
        for player, info in network_data['players'].items():
            pos = info['position']
            if pos in positions:
                x, y = positions[pos]
            else:
                # Default position
                x, y = 50, 40
            
            player_positions[player] = (x, y)
            plt.scatter(x, y, s=500, c='blue', alpha=0.7)
            plt.text(x, y, player.split()[-1], ha='center', va='center', 
                    fontsize=8, color='white', weight='bold')
        
        # Draw passing connections
        for connection, count in network_data['passes'].items():
            if count < 5:  # Only show significant connections
                continue
                
            passer, recipient = connection.split('->')
            if passer in player_positions and recipient in player_positions:
                x1, y1 = player_positions[passer]
                x2, y2 = player_positions[recipient]
                
                # Line width based on pass count
                width = min(count / 10, 5)
                plt.plot([x1, x2], [y1, y2], 'gray', 
                        linewidth=width, alpha=0.6)
        
        plt.title(f'{team_name} - Passing Network', fontsize=16)
        plt.xlim(-5, 125)
        plt.ylim(-5, 85)
        plt.axis('off')
        
        plt.tight_layout()
        plt.show()
    
    def analyze_shooting_efficiency(self, competition_id: int, season_id: int, 
                                  min_shots: int = 20) -> pd.DataFrame:
        """Analyze shooting efficiency across all players in a competition"""
        player_stats = self.fetcher.get_player_season_stats(competition_id, season_id)
        
        # Filter players with minimum shots
        shooters = player_stats[player_stats['shots'] >= min_shots].copy()
        
        # Calculate efficiency metrics
        shooters['goals_per_shot'] = shooters['goals'] / shooters['shots']
        shooters['xg_per_shot'] = shooters['xg'] / shooters['shots']
        shooters['shooting_overperformance'] = shooters['goals'] - shooters['xg']
        shooters['shot_accuracy'] = shooters['shots_on_target'] / shooters['shots'] * 100
        
        # Sort by shooting overperformance
        shooters = shooters.sort_values('shooting_overperformance', ascending=False)
        
        return shooters[['player_name', 'team_name', 'position', 'goals', 'xg', 
                        'shots', 'goals_per_shot', 'xg_per_shot', 
                        'shooting_overperformance', 'shot_accuracy']]
    
    def analyze_creative_players(self, competition_id: int, season_id: int,
                               min_passes: int = 500) -> pd.DataFrame:
        """Identify most creative players based on passing and chance creation"""
        player_stats = self.fetcher.get_player_season_stats(competition_id, season_id)
        
        # Filter players with minimum passes
        creators = player_stats[player_stats['passes'] >= min_passes].copy()
        
        # Calculate creative metrics
        creators['assists_per_90'] = (creators['assists'] / creators['minutes_played']) * 90
        creators['key_passes_per_90'] = (creators['key_passes'] / creators['minutes_played']) * 90
        creators['xa_per_90'] = (creators['xa'] / creators['minutes_played']) * 90
        creators['creative_actions_per_90'] = (
            (creators['assists'] + creators['key_passes']) / creators['minutes_played']
        ) * 90
        
        # Creative efficiency
        creators['assist_rate'] = creators['assists'] / (creators['assists'] + creators['key_passes']) * 100
        
        # Sort by creative actions
        creators = creators.sort_values('creative_actions_per_90', ascending=False)
        
        return creators[['player_name', 'team_name', 'position', 'assists', 'xa',
                        'key_passes', 'assists_per_90', 'xa_per_90', 
                        'key_passes_per_90', 'creative_actions_per_90', 'assist_rate']]
    
    def analyze_defensive_players(self, competition_id: int, season_id: int,
                                min_minutes: int = 900) -> pd.DataFrame:
        """Analyze defensive performance metrics"""
        player_stats = self.fetcher.get_player_season_stats(competition_id, season_id)
        
        # Filter defenders and defensive midfielders
        defenders = player_stats[
            (player_stats['position'].str.contains('Back|Defender', case=False, na=False)) |
            (player_stats['position'].str.contains('Defensive Midfield', case=False, na=False))
        ]
        defenders = defenders[defenders['minutes_played'] >= min_minutes].copy()
        
        # Calculate defensive metrics per 90
        defenders['tackles_per_90'] = (defenders['tackles'] / defenders['minutes_played']) * 90
        defenders['interceptions_per_90'] = (defenders['interceptions'] / defenders['minutes_played']) * 90
        defenders['clearances_per_90'] = (defenders['clearances'] / defenders['minutes_played']) * 90
        defenders['defensive_actions_per_90'] = (
            (defenders['tackles'] + defenders['interceptions'] + defenders['clearances']) / 
            defenders['minutes_played']
        ) * 90
        
        # Sort by total defensive actions
        defenders = defenders.sort_values('defensive_actions_per_90', ascending=False)
        
        return defenders[['player_name', 'team_name', 'position', 'games_played',
                         'tackles_per_90', 'interceptions_per_90', 'clearances_per_90',
                         'defensive_actions_per_90', 'fouls', 'cards_yellow', 'cards_red']]
    
    def generate_scouting_report(self, player_name: str, match_ids: List[int] = None) -> Dict:
        """Generate comprehensive scouting report for a player"""
        # Get player performance data
        performance = self.analyze_player_performance(player_name)
        
        if 'error' in performance:
            return performance
        
        report = {
            'player_name': player_name,
            'summary': {
                'games_analyzed': performance['career_stats']['games_played'],
                'total_minutes': performance['career_stats']['minutes_played'],
                'goals': performance['career_stats']['goals'],
                'assists': performance['career_stats']['assists'],
                'goal_contributions_per_90': (
                    performance['per_90_stats']['goals_per_90'] + 
                    performance['per_90_stats']['assists_per_90']
                )
            },
            'strengths': [],
            'weaknesses': [],
            'style_traits': []
        }
        
        # Analyze strengths and weaknesses
        per_90 = performance['per_90_stats']
        efficiency = performance['efficiency_metrics']
        
        # Scoring ability
        if per_90['goals_per_90'] > 0.5:
            report['strengths'].append("Elite goal scorer")
        elif per_90['goals_per_90'] > 0.3:
            report['strengths'].append("Good goal threat")
        
        # Creativity
        if per_90['assists_per_90'] > 0.3:
            report['strengths'].append("Excellent creator")
        elif per_90['key_passes_per_90'] > 2:
            report['strengths'].append("Creates chances regularly")
        
        # Shooting
        if efficiency['shot_accuracy'] > 40:
            report['strengths'].append("Accurate shooter")
        elif efficiency['shot_accuracy'] < 25:
            report['weaknesses'].append("Poor shot accuracy")
        
        # xG performance
        if efficiency['xg_overperformance'] > 5:
            report['strengths'].append("Clinical finisher (outperforms xG)")
        elif efficiency['xg_overperformance'] < -5:
            report['weaknesses'].append("Underperforms expected goals")
        
        # Playing style
        if per_90['shots_per_90'] > 3:
            report['style_traits'].append("High volume shooter")
        
        if efficiency['pass_completion'] > 85:
            report['style_traits'].append("Reliable passer")
        elif efficiency['pass_completion'] < 70:
            report['style_traits'].append("Risk-taking passer")
        
        if per_90['tackles_per_90'] > 2:
            report['style_traits'].append("Active defender")
        
        # Get match-specific insights if provided
        if match_ids:
            match_performances = []
            for match_id in match_ids[:5]:  # Limit to 5 matches
                try:
                    match_stats = self.fetcher.get_player_match_stats(match_id)
                    player_match = match_stats[match_stats['player_name'] == player_name]
                    if not player_match.empty:
                        match_performances.append(player_match.iloc[0].to_dict())
                except:
                    continue
            
            report['recent_matches'] = match_performances
        
        return report