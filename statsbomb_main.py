# statsbomb_main.py
"""Main application using only StatsBomb data"""

import argparse
import pandas as pd
from statsbomb_fetcher import StatsBombFetcher
from statsbomb_analyzer import StatsBombAnalyzer
import matplotlib.pyplot as plt


class StatsBombTransferAnalyzer:
    """Transfer analyzer using only StatsBomb data"""
    
    def __init__(self):
        self.fetcher = StatsBombFetcher(max_workers=10)  # Use threading
        self.analyzer = StatsBombAnalyzer()
        self.current_competition = None
        self.current_season = None
    
    def list_competitions(self):
        """List all available competitions"""
        competitions = self.fetcher.get_competitions()
        
        # Group by competition
        grouped = competitions.groupby('competition_name')['season_name'].apply(list).reset_index()
        
        print("\nAvailable Competitions:")
        print("="*60)
        for _, comp in grouped.iterrows():
            print(f"\n{comp['competition_name']}:")
            for season in comp['season_name']:
                print(f"  - {season}")
    
    def set_competition(self, competition_name: str, season_name: str):
        """Set the current competition and season to analyze"""
        competitions = self.fetcher.get_competitions()
        
        match = competitions[
            (competitions['competition_name'] == competition_name) &
            (competitions['season_name'] == season_name)
        ]
        
        if match.empty:
            print(f"Competition '{competition_name}' season '{season_name}' not found")
            return False
        
        self.current_competition = match.iloc[0]
        print(f"Set to: {competition_name} - {season_name}")
        return True
    
    def analyze_player(self, player_name: str):
        """Detailed analysis of a specific player"""
        if not self.current_competition:
            print("Please set competition first using --competition and --season")
            return
        
        analysis = self.analyzer.analyze_player_performance(
            player_name,
            self.current_competition['competition_name'],
            self.current_competition['season_name']
        )
        
        if 'error' in analysis:
            print(f"Player '{player_name}' not found in this competition")
            return
        
        # Display analysis
        print(f"\n{'='*60}")
        print(f"PLAYER ANALYSIS: {player_name}")
        print(f"Competition: {self.current_competition['competition_name']} {self.current_competition['season_name']}")
        print('='*60)
        
        stats = analysis['career_stats']
        per_90 = analysis['per_90_stats']
        efficiency = analysis['efficiency_metrics']
        
        print(f"\nBasic Stats:")
        print(f"  Games Played: {stats['games_played']}")
        print(f"  Minutes: {stats['minutes_played']}")
        print(f"  Goals: {stats['goals']} (xG: {stats['xg']:.2f})")
        print(f"  Assists: {stats['assists']} (xA: {stats['xa']:.2f})")
        
        print(f"\nPer 90 Minutes:")
        print(f"  Goals: {per_90['goals_per_90']:.2f}")
        print(f"  Assists: {per_90['assists_per_90']:.2f}")
        print(f"  xG: {per_90['xg_per_90']:.2f}")
        print(f"  xA: {per_90['xa_per_90']:.2f}")
        print(f"  Shots: {per_90['shots_per_90']:.2f}")
        print(f"  Key Passes: {per_90['key_passes_per_90']:.2f}")
        
        print(f"\nEfficiency:")
        print(f"  Shot Accuracy: {efficiency['shot_accuracy']:.1f}%")
        print(f"  Pass Completion: {efficiency['pass_completion']:.1f}%")
        print(f"  Goals/Shot: {efficiency['goals_per_shot']:.3f}")
        print(f"  xG Over/Under: {efficiency['xg_overperformance']:+.2f}")
        
        # Generate scouting insights
        report = self.analyzer.generate_scouting_report(player_name)
        
        if 'strengths' in report:
            print(f"\nStrengths:")
            for strength in report['strengths']:
                print(f"  ✓ {strength}")
        
        if 'weaknesses' in report:
            print(f"\nWeaknesses:")
            for weakness in report['weaknesses']:
                print(f"  ✗ {weakness}")
        
        if 'style_traits' in report:
            print(f"\nPlaying Style:")
            for trait in report['style_traits']:
                print(f"  • {trait}")
    
    def find_top_performers(self, metric: str = 'goals', position: str = None, top_n: int = 10):
        """Find top performers in current competition"""
        if not self.current_competition:
            print("Please set competition first")
            return
        
        # Get all player stats
        all_players = self.fetcher.get_player_season_stats(
            self.current_competition['competition_id'],
            self.current_competition['season_id']
        )
        
        if all_players.empty:
            print("No player data available")
            return
        
        # Filter by position if specified
        if position:
            all_players = all_players[
                all_players['position'].str.contains(position, case=False, na=False)
            ]
        
        # Filter by minimum playing time
        all_players = all_players[all_players['minutes_played'] >= 450]
        
        # Sort by metric
        if metric in all_players.columns:
            top_players = all_players.nlargest(top_n, metric)
        else:
            print(f"Metric '{metric}' not found")
            return
        
        print(f"\nTop {top_n} by {metric}:")
        print("="*80)
        
        display_cols = ['player_name', 'team_name', 'position', 'games_played', metric]
        
        # Add related metrics
        if metric == 'goals':
            display_cols.extend(['xg', 'goals_per_90'])
        elif metric == 'assists':
            display_cols.extend(['xa', 'assists_per_90'])
        elif metric == 'xg':
            display_cols.extend(['goals', 'xg_per_90'])
        
        print(top_players[display_cols].to_string(index=False))
    
    def find_similar_players(self, player_name: str, top_n: int = 5):
        """Find players with similar playing styles"""
        if not self.current_competition:
            print("Please set competition first")
            return
        
        similar = self.analyzer.find_similar_players_statsbomb(
            player_name, 
            top_n=top_n
        )
        
        if similar.empty:
            print(f"Could not find similar players to {player_name}")
            return
        
        print(f"\nPlayers similar to {player_name}:")
        print("="*60)
        print(similar.to_string(index=False))
    
    def analyze_shooters(self, min_shots: int = 20):
        """Analyze shooting efficiency"""
        if not self.current_competition:
            print("Please set competition first")
            return
        
        shooters = self.analyzer.analyze_shooting_efficiency(
            self.current_competition['competition_id'],
            self.current_competition['season_id'],
            min_shots=min_shots
        )
        
        print(f"\nShooting Efficiency Analysis (min {min_shots} shots):")
        print("="*80)
        print(shooters.head(15).to_string(index=False))
    
    def analyze_creators(self, min_passes: int = 300):
        """Analyze creative players"""
        if not self.current_competition:
            print("Please set competition first")
            return
        
        creators = self.analyzer.analyze_creative_players(
            self.current_competition['competition_id'],
            self.current_competition['season_id'],
            min_passes=min_passes
        )
        
        print(f"\nCreative Players Analysis (min {min_passes} passes):")
        print("="*80)
        print(creators.head(15).to_string(index=False))
    
    def analyze_defenders(self, min_minutes: int = 900):
        """Analyze defensive players"""
        if not self.current_competition:
            print("Please set competition first")
            return
        
        defenders = self.analyzer.analyze_defensive_players(
            self.current_competition['competition_id'],
            self.current_competition['season_id'],
            min_minutes=min_minutes
        )
        
        print(f"\nDefensive Players Analysis (min {min_minutes} minutes):")
        print("="*80)
        print(defenders.head(15).to_string(index=False))
    
    def compare_players(self, player_names: list):
        """Compare multiple players"""
        comparison = self.analyzer.compare_players(player_names)
        
        if comparison.empty:
            print("No data found for comparison")
            return
        
        print(f"\nPlayer Comparison:")
        print("="*80)
        print(comparison.to_string(index=False))
        
        # Create visualization
        self.analyzer.visualize_player_radar(player_names)
    
    def analyze_match(self, home_team: str, away_team: str):
        """Analyze a specific match"""
        if not self.current_competition:
            print("Please set competition first")
            return
        
        # Find the match
        matches = self.fetcher.get_matches(
            self.current_competition['competition_id'],
            self.current_competition['season_id']
        )
        
        match = matches[
            (matches['home_team'].apply(lambda x: x['home_team_name']) == home_team) &
            (matches['away_team'].apply(lambda x: x['away_team_name']) == away_team)
        ]
        
        if match.empty:
            print(f"Match {home_team} vs {away_team} not found")
            return
        
        match_id = match.iloc[0]['match_id']
        
        # Get match stats
        player_stats = self.fetcher.get_player_match_stats(match_id)
        
        print(f"\nMatch Analysis: {home_team} vs {away_team}")
        print("="*60)
        
        # Top performers
        print("\nTop Performers:")
        top_performers = player_stats.nlargest(5, 'touches')[
            ['player_name', 'team_name', 'goals', 'assists', 'passes', 'shots', 'touches']
        ]
        print(top_performers.to_string(index=False))
        
        # Generate visualizations
        print("\nGenerating passing network...")
        self.analyzer.visualize_passing_network(match_id, home_team)


def main():
    parser = argparse.ArgumentParser(description='StatsBomb Soccer Analysis Tool')
    
    # Commands
    parser.add_argument('--list', action='store_true', help='List available competitions')
    parser.add_argument('--competition', type=str, help='Competition name')
    parser.add_argument('--season', type=str, help='Season name')
    
    # Analysis options
    parser.add_argument('--player', type=str, help='Analyze specific player')
    parser.add_argument('--top', type=str, choices=['goals', 'assists', 'xg', 'xa', 'shots'],
                       help='Show top performers by metric')
    parser.add_argument('--position', type=str, help='Filter by position')
    parser.add_argument('--similar', type=str, help='Find similar players')
    parser.add_argument('--compare', nargs='+', help='Compare multiple players')
    parser.add_argument('--shooters', action='store_true', help='Analyze shooting efficiency')
    parser.add_argument('--creators', action='store_true', help='Analyze creative players')
    parser.add_argument('--defenders', action='store_true', help='Analyze defensive players')
    parser.add_argument('--match', nargs=2, metavar=('HOME', 'AWAY'), help='Analyze specific match')
    parser.add_argument('--top-n', type=int, default=10, help='Number of results to show')
    
    args = parser.parse_args()
    
    # Initialize analyzer
    analyzer = StatsBombTransferAnalyzer()
    
    # List competitions
    if args.list:
        analyzer.list_competitions()
        return
    
    # Set competition if specified
    if args.competition and args.season:
        if not analyzer.set_competition(args.competition, args.season):
            return
    
    # Execute analysis commands
    if args.player:
        analyzer.analyze_player(args.player)
    
    elif args.top:
        analyzer.find_top_performers(
            metric=args.top,
            position=args.position,
            top_n=args.top_n
        )
    
    elif args.similar:
        analyzer.find_similar_players(args.similar, top_n=args.top_n)
    
    elif args.compare:
        analyzer.compare_players(args.compare)
    
    elif args.shooters:
        analyzer.analyze_shooters()
    
    elif args.creators:
        analyzer.analyze_creators()
    
    elif args.defenders:
        analyzer.analyze_defenders()
    
    elif args.match:
        analyzer.analyze_match(args.match[0], args.match[1])
    
    else:
        print("No analysis command specified. Use -h for help.")


if __name__ == "__main__":
    main()