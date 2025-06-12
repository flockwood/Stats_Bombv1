# StatsBomb Soccer Analyzer

A Python tool for analyzing soccer/football data using StatsBomb's free open data.

## Features

- **Player Analysis**: Detailed performance metrics including xG, xA, shooting efficiency
- **Player Comparison**: Compare multiple players across various metrics
- **Top Performers**: Find best players by goals, assists, xG, etc.
- **Similar Players**: Find players with similar playing styles
- **Shooting Analysis**: Identify clinical finishers and shooting efficiency
- **Creative Analysis**: Find the best playmakers and chance creators
- **Defensive Analysis**: Analyze tackles, interceptions, and defensive actions
- **Match Analysis**: Detailed match statistics and passing networks
- **Visualizations**: Radar charts, heatmaps, and passing networks

## Available Data

StatsBomb provides free data for:
- FIFA World Cup (2018, 2022)
- UEFA Euro (2020)
- UEFA Women's Euro (2022)
- FA Women's Super League (multiple seasons)
- NWSL (2018)
- Premier League (2003/2004)
- La Liga (2004/2005 - 2019/2020)
- Bundesliga (2015/2016 - 2019/2020)
- Serie A (2015/2016 - 2019/2020)
- Ligue 1 (2015/2016 - 2019/2020)
- Champions League (various seasons)

## Installation

```bash
# Clone or download the files
mkdir statsbomb-soccer-analyzer
cd statsbomb-soccer-analyzer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### List Available Competitions
```bash
python statsbomb_main.py --list
```

### Set Competition and Analyze Players
```bash
# Set to Premier League 2003/2004
python statsbomb_main.py --competition "Premier League" --season "2003/2004" --player "Thierry Henry"

# Analyze World Cup 2022
python statsbomb_main.py --competition "FIFA World Cup" --season "2022" --player "Lionel Messi"
```

### Find Top Performers
```bash
# Top scorers
python statsbomb_main.py --competition "La Liga" --season "2014/2015" --top goals

# Top assisters (forwards only)
python statsbomb_main.py --competition "La Liga" --season "2014/2015" --top assists --position Forward

# Top xG performers
python statsbomb_main.py --competition "Premier League" --season "2003/2004" --top xg --top-n 20
```

### Compare Players
```bash
python statsbomb_main.py --competition "La Liga" --season "2014/2015" --compare "Lionel Messi" "Cristiano Ronaldo" "Neymar"
```

### Find Similar Players
```bash
python statsbomb_main.py --competition "Premier League" --season "2003/2004" --similar "Thierry Henry"
```

### Analyze Playing Styles
```bash
# Clinical finishers
python statsbomb_main.py --competition "FIFA World Cup" --season "2018" --shooters

# Creative players
python statsbomb_main.py --competition "La Liga" --season "2018/2019" --creators

# Best defenders
python statsbomb_main.py --competition "Serie A" --season "2018/2019" --defenders
```

### Analyze Specific Match
```bash
python statsbomb_main.py --competition "FIFA World Cup" --season "2018" --match "France" "Croatia"
```

## Examples

### Example 1: Find the most clinical finisher in Premier League 2003/04
```bash
python statsbomb_main.py --competition "Premier League" --season "2003/2004" --shooters
```

### Example 2: Compare Messi across different seasons
```python
from statsbomb_analyzer import StatsBombAnalyzer

analyzer = StatsBombAnalyzer()

# Get Messi's stats from different seasons
seasons = ["2011/2012", "2014/2015", "2018/2019"]
for season in seasons:
    stats = analyzer.analyze_player_performance("Lionel Messi", "La Liga", season)
    print(f"{season}: {stats['career_stats']['goals']} goals from {stats['career_stats']['xg']:.1f} xG")
```

### Example 3: Find undervalued players (high xG, low goals)
```python
from statsbomb_fetcher import StatsBombFetcher

fetcher = StatsBombFetcher()

# Get La Liga 2018/2019 data
competitions = fetcher.get_competitions()
la_liga = competitions[(competitions['competition_name'] == 'La Liga') & 
                      (competitions['season_name'] == '2018/2019')].iloc[0]

# Get all players
players = fetcher.get_player_season_stats(la_liga['competition_id'], la_liga['season_id'])

# Find players underperforming xG
underperformers = players[players['minutes_played'] > 1000].copy()
underperformers['xg_underperformance'] = underperformers['xg'] - underperformers['goals']
underperformers = underperformers.nlargest(10, 'xg_underperformance')

print("Players who should have scored more:")
print(underperformers[['player_name', 'goals', 'xg', 'xg_underperformance']])
```

## Data Structure

The analyzer provides access to:

**Basic Stats**: Goals, Assists, Minutes Played
**Advanced Metrics**: xG, xA, Key Passes, Shot Accuracy
**Per 90 Metrics**: All stats normalized to 90 minutes
**Efficiency Metrics**: Goals per Shot, Pass Completion %, xG Over/Underperformance
**Defensive Metrics**: Tackles, Interceptions, Clearances
**Event Data**: Every pass, shot, tackle with pitch coordinates

## Limitations

- Data is historical (not current season)
- Some competitions have limited seasons available
- Player names must match exactly (case-sensitive)
- Some visualizations require specific match IDs

## License

This tool uses StatsBomb's open data. Please refer to StatsBomb's license for data usage terms.