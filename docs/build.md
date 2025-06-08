# Building

## Building From Source

Create a Python virtual environment, activate it, update pip, and install requirements:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Set the environment variable and run Selectarr:

```bash
export JELLYFIN_API_KEY=your_api_key_here
python run.py --help
```

## Alternative Build: Container Image

Build the image:

```bash
docker build -t selectarr .
```

Run the container:

```bash
docker run -e JELLYFIN_API_KEY=your_api_key_here -v $(pwd)/config.yml:/app/config.yml selectarr
```

Append options like --debug or --dry-run:

```bash
docker run -e JELLYFIN_API_KEY=your_api_key_here -v $(pwd)/config.yml:/app/config.yml selectarr --help
```
