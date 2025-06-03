import requests
import pandas as pd
from datetime import datetime, timedelta

BASE_URL = 'https://api.sofascore.com/api/v1'

def get_json(url):
    r = requests.get(url)
    r.raise_for_status()
    return r.json()

def fetch_events(date):
    url = f"{BASE_URL}/sport/tennis/scheduled-events/{date.strftime('%Y-%m-%d')}"
    data = get_json(url)
    events = [e for e in data.get('events', []) if e['tournament']['category']['slug'] == 'itf-women']
    return events

def fetch_event_details(event_id):
    event = get_json(f"{BASE_URL}/event/{event_id}")['event']
    stats = get_json(f"{BASE_URL}/event/{event_id}/statistics").get('statistics', [])
    pbp = get_json(f"{BASE_URL}/event/{event_id}/point-by-point").get('pointByPoint', [])
    return event, stats, pbp

def normalize_name(name):
    return name.lower().replace(' ', '_').replace('%', 'pct')

def parse_statistics(stats_list):
    result = {}
    for entry in stats_list:
        period = entry['period'].lower()
        for group in entry.get('groups', []):
            for item in group.get('statisticsItems', []):
                key = f"{period}_{normalize_name(item['name'])}"
                result[f"{key}_home"] = item.get('home')
                result[f"{key}_away"] = item.get('away')
    return result

def parse_games(event_id, pbp):
    rows = []
    for set_data in pbp:
        set_number = set_data['set']
        for game in set_data.get('games', []):
            row = {
                'event_id': event_id,
                'set': set_number,
                'game': game.get('game'),
                'home_score': game.get('score', {}).get('homeScore'),
                'away_score': game.get('score', {}).get('awayScore'),
                'points': str([(p.get('homePoint'), p.get('awayPoint')) for p in game.get('points', [])])
            }
            rows.append(row)
    return rows

def main(start_date=datetime(2019, 1, 1), end_date=datetime(2019, 1, 5), limit=None):
    delta = timedelta(days=1)

    matches = []
    games = []

    current = start_date
    while current <= end_date:
        events = fetch_events(current)
        if limit:
            events = events[:limit]
        for e in events:
            event_id = e['id']
            event, stats, pbp = fetch_event_details(event_id)
            row = {
                'event_id': event_id,
                'slug': e['slug'],
                'home_team': e['homeTeam']['name'],
                'away_team': e['awayTeam']['name'],
                'start_timestamp': event.get('startTimestamp'),
            }
            time_info = event.get('time', {})
            row['match_duration'] = time_info.get('current')
            row['set1_duration'] = time_info.get('period1')
            row['set2_duration'] = time_info.get('period2')
            row['set3_duration'] = time_info.get('period3')
            row.update(parse_statistics(stats))
            matches.append(row)
            games.extend(parse_games(event_id, pbp))
        current += delta

    matches_df = pd.DataFrame(matches)
    games_df = pd.DataFrame(games)

    with pd.ExcelWriter('itf_women_2019_01_01_05.xlsx') as writer:
        matches_df.to_excel(writer, index=False, sheet_name='matches')
        games_df.to_excel(writer, index=False, sheet_name='games')

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Scrape ITF Women matches from SofaScore.')
    parser.add_argument('--start', default='2019-01-01', help='Start date YYYY-MM-DD')
    parser.add_argument('--end', default='2019-01-05', help='End date YYYY-MM-DD')
    parser.add_argument('--limit', type=int, default=None, help='Limit matches per day for quick runs')
    args = parser.parse_args()
    start = datetime.strptime(args.start, '%Y-%m-%d')
    end = datetime.strptime(args.end, '%Y-%m-%d')
    main(start, end, limit=args.limit)
