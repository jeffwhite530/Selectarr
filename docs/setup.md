# Setup & Usage

## Installation

Create a Python virtual environment, activate it, update pip, and install requirements:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Setup

1. Get API key from Jellyfin: Settings --> Dashboard --> API Keys
1. Create a `config.yml` file with your Jellyfin server details and collection definitions

## Usage

Set environment variable and run:

```bash
export JELLYFIN_API_KEY=your_api_key_here
python run.py --help
```

For debug output:

```bash
python run.py --debug
```

## Alternative Setup: Docker

Build image:

```bash
docker build -t selectarr .
```

Run container:

```bash
docker run -e JELLYFIN_API_KEY=your_api_key_here -v $(pwd)/config.yml:/app/config.yml selectarr
```

For debug output:

```bash
docker run -e JELLYFIN_API_KEY=your_api_key_here -v $(pwd)/config.yml:/app/config.yml selectarr --debug
```
