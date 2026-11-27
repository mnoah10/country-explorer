# 🌍 Country Explorer

**Search, filter and sort every country in the world, and see the live weather in its capital.**

> ### Quick access for the grader
>
> | Item | Value |
> |---|---|
> | **Live app (load balancer)** | http://13.40.170.230 |
> | Web01 (direct) | http://18.171.185.250 |
> | Web02 (direct) | http://18.175.44.254 |
> | GitHub repository | https://github.com/mnoah10/country-explorer |
> | Demo video | [https://youtu.be/NiMr0uCXlQ8] |
> | **REST Countries API key** | Given in the **submission comment** (kept out of this public repository on purpose, as the assignment requires) |
> | Open-Meteo API key | None required |
> | App login | None required (the app has no authentication) |

---

## Table of contents

1. [Description](#1-description)
2. [Features](#2-features)
3. [APIs used](#3-apis-used)
4. [Architecture](#4-architecture)
5. [Run it locally](#5-run-it-locally)
6. [Deployment](#6-deployment)
7. [Testing](#7-testing)
8. [Challenges and how I solved them](#8-challenges-and-how-i-solved-them)
9. [Security notes](#9-security-notes)
10. [Project structure](#10-project-structure)
11. [Credits](#11-credits)

---

## 1. Description

Country Explorer is a web application for exploring the countries of the world. Users can search by name, filter by region, sort by name, population or area, and click any country to see the **current weather in its capital**. It is useful for trip planning, geography study and quick comparisons between countries.

The application is deployed on two web servers (Web01 and Web02) behind a load balancer (Lb01). The page footer shows which server answered each request, which makes the load balancing visible to users.

## 2. Features

**Core features**

- Live search by country name
- Filter by region (Africa, Americas, Asia, Europe, Oceania and others)
- Sort by name (A to Z), population (high to low) or area (high to low)
- Click a country to see its capital's current temperature and wind speed
- Flag, capital, population and area shown for all 254 entries
- Clear error messages when an external API is unavailable or returns bad data
- Footer shows which server handled the request

**Bonus work**

- In-memory ing cachof API responses (countries for 24 hours, weather for 10 minutes), which cuts load times and protects the limited free-plan API quota
- Input validation on the weather endpoint (non-numeric coordinates are rejected with HTTP 400)
- Cross-site scripting (XSS) protection: text coming from the APIs is escaped before it is inserted into the page
- API key kept in an environment variable and excluded from Git

## 3. APIs used

| API | Purpose | Documentation |
|---|---|---|
| **REST Countries v5** | Country data: names, capitals, region, population, area, flags and coordinates | https://restcountries.com/docs/countries |
| **Open-Meteo** | Current weather for a latitude and longitude (no key needed) | https://open-meteo.com/en/docs |

Thank you to the REST Countries and Open-Meteo teams for providing these APIs.

## 4. Architecture

```
Browser ──> Lb01 (HAProxy, round robin) ──┬──> Web01: Nginx ──> Gunicorn ──> Flask app
                                          └──> Web02: Nginx ──> Gunicorn ──> Flask app
                                                                     │
                                                                     └──> REST Countries and Open-Meteo APIs
```

The browser never calls the external APIs directly. It calls the Flask backend, and the backend calls the APIs. This keeps the API key on the server and avoids browser CORS problems.

| Endpoint | What it does |
|---|---|
| `GET /` | Serves the frontend page |
| `GET /api/countries` | Returns all countries, fetched in pages of 100 from the API and then cached |
| `GET /api/weather?lat=..&lon=..` | Returns the current weather for the given coordinates |
| `GET /api/server` | Returns the hostname of the server that answered (used to prove load balancing) |

## 5. Run it locally

**Requirements:** Python 3.8 or newer, Git, and a free REST Countries API key (https://restcountries.com/sign-up).

```bash
git clone https://github.com/mnoah10/country-explorer.git
cd country-explorer
python -m venv venv
```

Activate the virtual environment:

```bash
# Windows (PowerShell)
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

Create a file named `.env` in the project folder with one line:

```
RESTCOUNTRIES_API_KEY=your_key_here
```

Start the app, then open http://localhost:8000:

```bash
python app.py
```

`gunicorn` is used on the Linux servers and does not run on Windows. `python app.py` works on every system.

## 6. Deployment

The app runs on Ubuntu 20.04 servers. Replace `your_key_here` with the real API key.

### 6.1 Web servers (done on both Web01 and Web02)

Install the tools and download the code:

```bash
sudo apt update
sudo apt install -y python3-venv git nginx
git clone https://github.com/mnoah10/country-explorer.git
cd country-explorer
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

Store the API key in a `.env` file on the server (it is not in Git):

```bash
echo 'RESTCOUNTRIES_API_KEY=your_key_here' > .env
chmod 600 .env
```

Run the app as a background service. Create `/etc/systemd/system/country.service`:

```ini
[Unit]
Description=Country Explorer
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/country-explorer
ExecStart=/home/ubuntu/country-explorer/venv/bin/gunicorn -w 1 --threads 4 -b 127.0.0.1:8000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now country
```

One Gunicorn worker with several threads is used on purpose, so each server keeps a single cache and makes fewer calls to the limited API quota.

Put Nginx in front of the app. In `/etc/nginx/sites-available/default`:

```nginx
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    add_header X-Served-By $hostname always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl reload nginx
```

The `X-Served-By` header and the `/api/server` endpoint both show which web server replied.

### 6.2 Load balancer (Lb01)

```bash
sudo apt update
sudo apt install -y haproxy
```

Added to the end of `/etc/haproxy/haproxy.cfg`:

```
frontend http_front
    bind *:80
    default_backend app_servers

backend app_servers
    balance roundrobin
    option httpchk GET /api/server
    server web01 18.171.185.250:80 check
    server web02 18.175.44.254:80 check
```

```bash
sudo haproxy -c -f /etc/haproxy/haproxy.cfg
sudo systemctl restart haproxy
sudo systemctl enable haproxy
```

How it works:

- `balance roundrobin` sends requests to Web01 and Web02 in turn.
- `option httpchk GET /api/server` with `check` makes HAProxy probe each server. A server that stops answering is taken out of rotation, and traffic continues on the other one.

### 6.3 Updating the app after a code change

On each web server:

```bash
cd ~/country-explorer
git pull
sudo systemctl restart country
```

## 7. Testing

### 7.1 Load balancing

Each request sent to the load balancer is answered by a different web server in turn. From any machine:

```bash
for i in 1 2 3 4 5 6; do curl -s http://13.40.170.230/api/server; echo; done
```

Expected result, with the two server names alternating:

```
{"server":"7359-web-01"}
{"server":"7359-web-02"}
{"server":"7359-web-01"}
{"server":"7359-web-02"}
{"server":"7359-web-01"}
{"server":"7359-web-02"}
```

The response header also names the server:

```bash
curl -I http://13.40.170.230
```

```
X-Served-By: 7359-web-01    (or 7359-web-02)
```

The footer of the web page shows the same information under "Served by".

### 7.2 Each web server on its own

Both servers were checked directly and returned HTTP 200 with the app page and their own name in `X-Served-By`:

```bash
curl -I http://18.171.185.250    # X-Served-By: 7359-web-01
curl -I http://18.175.44.254     # X-Served-By: 7359-web-02
```

### 7.3 Failover

Stop the app on Web01 and send requests through the load balancer. The health check removes Web01 from rotation and every request is answered by Web02:

```bash
sudo systemctl stop country      # on Web01
for i in 1 2 3 4; do curl -s http://13.40.170.230/api/server; echo; done
sudo systemctl start country     # restore Web01
```

### 7.4 Application behaviour

| Test | Expected result |
|---|---|
| Open the load balancer address | Page loads and shows 254 countries |
| Type in the search box | The list filters as you type |
| Choose a region | Only countries from that region are shown |
| Change the sort option | The list reorders by name, population or area |
| Click a country | Capital name, temperature and wind speed are shown |
| Open `/api/weather?lat=abc` | HTTP 400 with `{"error": "Wrong coordinates"}` |
| API unavailable or key missing | A readable error message is shown instead of a blank page |

## 8. Challenges and how I solved them

| Challenge | Solution |
|---|---|
| The REST Countries v3.1 endpoint I started with was retired and returned a "deprecated" error | I read the new documentation and migrated to v5 (new hostname, API key sent in an `Authorization: Bearer` header, new response format). A `simplify()` function flattens each record so the frontend stays simple |
| Only 100 countries appeared instead of 254 | The free plan returns at most 100 per request. I added a loop that follows the API's `more` flag to fetch every page, and fixed a `return` placed inside the loop that stopped it after the first page |
| Area was labelled km² but the values were square miles | The request now asks for `area.kilometers` instead of `area.miles` |
| `Permission denied (publickey)` when connecting to the servers | My SSH private key was stored in my school container, not on my laptop, so I connected from the container |
| `nano` and `vi` were not installed on the servers | I created files with `echo` and `sudo tee` instead of an editor |
| The server showed an old static page instead of my app | The default Nginx config served `/var/www/html` before proxying. I removed the `root` and `index` lines so every path goes to the Flask app |
| `python dotenv` (with a space) in `requirements.txt` broke installation on the server | I corrected the package name to `python-dotenv` |
| The free API plan has a small monthly quota | I cached responses in memory and used a single Gunicorn worker per server |

## 9. Security notes

- The API key is read from the `RESTCOUNTRIES_API_KEY` environment variable and stored in `.env`, which is listed in `.gitignore`, so it is never pushed to GitHub.
- The key is given to the grader in the submission comment, not in this repository.
- Text coming from the APIs is escaped before being placed in the page (XSS protection).
- Weather coordinates are validated before they are used.
- The `.env` file on each server is readable only by its owner (`chmod 600`).

## 10. Project structure

```
country-explorer/
├── app.py              # Flask backend: API proxy, pagination, caching, validation
├── requirements.txt    # Python dependencies
├── static/
│   └── index.html      # Frontend: HTML, CSS and JavaScript
├── .gitignore          # Keeps .env and venv out of Git
└── README.md
```

## 11. Credits

- **REST Countries** for country data: https://restcountries.com
- **Open-Meteo** for weather data: https://open-meteo.com
- **Flask**: https://flask.palletsprojects.com
- **Requests**: https://requests.readthedocs.io
- **Gunicorn**: https://gunicorn.org
- **python-dotenv**: https://github.com/theskumar/python-dotenv
- **Nginx** (https://nginx.org) and **HAProxy** (https://www.haproxy.org) for serving and load balancing

Built by Noah Muyango.