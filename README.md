# RiftAnalyzerGG

A League of Legends performance analytics platform built with Python, FastAPI, React, TypeScript, and PostgreSQL.

## About

RiftAnalyzerGG is a personal side project focused on analyzing League of Legends match history, visualizing player statistics, and exploring machine learning techniques to identify patterns associated with winning and losing.

## Tech Stack

- **Frontend:** React, TypeScript, Vite
- **Backend:** Python, FastAPI
- **Database:** PostgreSQL, SQLAlchemy
- **Machine Learning:** scikit-learn, XGBoost
- **External API:** Riot Games API
- **Containerization:** Docker

## Planned Features

- Search for players using Riot ID
- Retrieve and store match history
- Visualize player and champion statistics
- Analyze gameplay performance
- Predict match outcomes using machine learning

## Project Status

The backend can sync Riot match details, participant statistics and timelines
into PostgreSQL, then serve or export a player's dataset for analysis.
See [backend setup and match collection](backend/docs/match_data.md) for migrations,
API examples, SQL queries, CSV export and tests.

The first analysis stage now extracts 10/15/20-minute timeline features and
returns statistical associations with sample sizes and uncertainty, separated
by position and patch. It also extracts phase progression, post-kill/death windows
and conservative mid-player sidelane proxies, with descriptive win/loss summaries.
See [personal match analysis](backend/docs/analysis.md)
for the API, feature definitions and limitations. LLM report generation is planned.

The [React + TypeScript frontend](frontend/README.md) provides player lookup,
champion/lane filtering, phase comparisons and evidence summaries in English.
Start the backend, then run `npm ci` and `npm run dev` from `frontend`.

## Disclaimer

RiftAnalyzerGG is an independent hobby project and is not endorsed by Riot Games.
