#!/usr/bin/env python3
import argparse
import json
import logging
import re
import smtplib
import ssl
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
REPORTS_DIR = ROOT / "reports"
LOGS_DIR = ROOT / "logs"
TRACKING_PATH = ROOT / "tracking.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DailyJobReport/1.0"

CV_SKILLS = [
    "python", "sql", "databricks", "pyspark", "spark", "airflow", "dbt",
    "snowflake", "kafka", "aws", "terraform", "docker", "etl", "elt",
    "data pipeline", "data warehouse", "data quality", "data modelling",
    "data modeling", "postgresql", "mysql", "sql server", "delta lake",
    "eventbridge", "sqs", "cloudwatch", "c#", "java", "typescript",
]

TITLE_KEYWORDS = [
    "data engineer", "analytics engineer", "data platform engineer",
    "big data engineer", "etl developer", "data infrastructure",
]

RELEVANT_TITLE_TOKENS = [
    "data engineer", "analytics engineer", "data platform", "data infrastructure",
    "big data", "etl", "data warehouse", "data architect", "database engineer",
    "databricks", "snowflake", "airflow", "dbt", "data pipeline",
    "analytics infrastructure", "data engineering", "data governance",
    "data management", "data ops", "dataops", "bi engineer",
    "business intelligence engineer", "data analytics", "data developer",
    "data services",
]

EXCLUDE_TITLE_TOKENS = [
    "support engineer", "sales engineer", "systems engineer", "security engineer",
    "network engineer", "test engineer", "field engineer", "solutions engineer",
    "data entry", "clinical data",
]

ELIGIBLE_TOKENS = ["worldwide", "anywhere", "global", "africa", "kenya", "emea", "remote"]
RESTRICTED_TOKENS = [
    "usa only", "us only", "united states", "canada only", "uk only",
    "europe only", "europe", "germany", "india", "latam", "brazil",
    "philippines", "australia", "japan", "singapore", "poland", "spain",
    "portugal", "france", "netherlands", "mexico", "argentina", "colombia",
]

KENYA_JOBS = [
    {
        "company": "Co-operative Bank of Kenya", "title": "Data Engineer",
        "location": "Nairobi", "type": "Onsite", "deadline": "9 Nov 2026",
        "stack": "SQL, Python/Scala, ETL/ELT, data quality",
        "url": "https://www.co-opbank.co.ke/careers/co-op-bank/data-engineer-8",
        "note": "Email jobs@co-opbank.co.ke with reference DE/IID/2026.",
    },
    {
        "company": "Co-operative Bank of Kenya", "title": "AI & Data Architect (stretch)",
        "location": "Nairobi", "type": "Onsite", "deadline": "9 Nov 2026",
        "stack": "Data architecture, governance, AI data readiness",
        "url": "https://www.myjobmag.co.ke/jobs/job-vacancies-at-co-operative-bank-of-kenya-5",
        "note": "Sibling roles: Data Scientist, AI Integration Engineer, AI QA (same deadline).",
    },
    {
        "company": "CloudFactory", "title": "Data Engineer",
        "location": "Nairobi", "type": "Hybrid", "deadline": "~10 Nov 2026",
        "stack": "Fivetran, dbt, Snowflake, Python, QuickSight",
        "url": "https://jobs.workable.com/view/wNZcnoNYXfdd82ETt9imXs/hybrid-data-engineer-in-nairobi-at-cloudfactory",
        "note": "Closest title/level fit in Kenya. Apply on Workable.",
    },
    {
        "company": "Prospect 33", "title": "Data Engineer (remote Kenya team)",
        "location": "Remote — Kenya", "type": "Remote", "deadline": "Hiring now",
        "stack": "SQL, Python, ETL, data platforms",
        "url": "https://www.linkedin.com/jobs/search/?keywords=Prospect%2033%20data%20engineer%20Kenya",
        "note": "New Kenya-based team for a Tier 1 US bank. Apply early.",
    },
    {
        "company": "Accelera Digital Group", "title": "Data Engineer — Data & AI",
        "location": "Nairobi", "type": "Hybrid", "deadline": "Open",
        "stack": "GCP, big data, Databricks/Spark, streaming",
        "url": "https://www.brightermonday.co.ke/listings/data-engineer-45dzzr",
        "note": "7+ years requested; frame breadth across four companies.",
    },
    {
        "company": "KCB Bank Kenya", "title": "Data Architect",
        "location": "Nairobi", "type": "Onsite", "deadline": "13 Nov 2026",
        "stack": "Enterprise data architecture, governance",
        "url": "https://www.myjobmag.co.ke/job/data-architect-kcb-bank-kenya-1",
        "note": "Stretch role; watch KCB for hands-on Data Engineer openings too.",
    },
    {
        "company": "Stanbic Bank Kenya", "title": "Data Engineer",
        "location": "Nairobi", "type": "Onsite", "deadline": "Verify deadline",
        "stack": "SQL, PL/SQL, Spark, pipelines",
        "url": "https://openedcareer.com/job/data-engineer-at-stanbic-bank-kenya/",
        "note": "Deadlines reported as 14 Oct / 6 Dec — confirm before applying.",
    },
    {
        "company": "Watu Credit", "title": "Data Engineer / Analytics Engineer",
        "location": "Nairobi / remote", "type": "Remote", "deadline": "Verify repost",
        "stack": "SQL, Python, dbt, GCP/BigQuery, streaming",
        "url": "https://builtin.com/job/data-engineer/11373209",
        "note": "Fresh repost reported; GCP is the main gap to address.",
    },
    {
        "company": "KEMRI", "title": "Data Manager (adjacent)",
        "location": "Nairobi", "type": "Onsite", "deadline": "20 Nov 2026",
        "stack": "Study data management, validation, secure storage",
        "url": "https://joballer.com/it-technology-jobs",
        "note": "Adjacent fallback; lower engineering ceiling.",
    },
    {
        "company": "I&M Bank", "title": "Assistant Manager, Data Scientist (adjacent)",
        "location": "Nairobi", "type": "Onsite", "deadline": "Verify",
        "stack": "ML models, predictive analytics",
        "url": "https://www.corporatestaffing.co.ke/category/banking-jobs-in-kenya/",
        "note": "Data science bridge role; watch I&M for DE titles.",
    },
    {
        "company": "M-KOPA", "title": "Data & platform roles — watch (6 open)",
        "location": "Nairobi / remote", "type": "Remote/hybrid", "deadline": "Rolling",
        "stack": "C#/.NET Azure microservices, credit analytics",
        "url": "https://www.m-kopa.com/careers/",
        "note": "C#/.NET Azure role is a direct match for your C# background.",
    },
    {
        "company": "Safaricom / M-PESA Africa", "title": "Data engineering roles — watch",
        "location": "Nairobi", "type": "Hybrid", "deadline": "Rolling",
        "stack": "Spark, Kafka, Airflow, AWS",
        "url": "https://www.safaricom.co.ke/careers",
        "note": "Big Data/CVM team hires repeatedly; check weekly.",
    },
    {
        "company": "Kenya Airways", "title": "Data Engineer — watch",
        "location": "Nairobi", "type": "Onsite", "deadline": "Rolling",
        "stack": "Python, SQL, AWS/Azure, Airflow",
        "url": "https://careers.kenya-airways.com",
        "note": "Last posting matched almost exactly; set an alert.",
    },
    {
        "company": "Cellulant", "title": "Data engineering roles — watch",
        "location": "Nairobi", "type": "Hybrid", "deadline": "Rolling",
        "stack": "AWS DMS/Glue, Airflow, Python",
        "url": "https://www.cellulant.io/open-roles",
        "note": "Payments data at scale; watch open roles.",
    },
]

PEOPLE = [
    ("Brian Ochieng", "Data Engineer — Big Data & CVM", "Safaricom PLC", "https://linkedin.com/in/bhochieng"),
    ("John Mekubo", "Data Engineer / Big Data & AI", "Safaricom PLC", "https://linkedin.com/in/jmekubo"),
    ("Lydiah Ng'endo", "Senior Data Engineer & BI Developer", "Safaricom PLC", "https://linkedin.com/in/lynnengendo"),
    ("Daniel Gitau", "Big Data Engineer", "Safaricom PLC", "https://linkedin.com/in/daniel-gitau-5a452994"),
    ("Christopher Wachira", "Data Engineer", "Cellulant", "https://linkedin.com/in/christopher-wachira-7bb9b11b1"),
    ("Ben Sang", "Principal Data Engineer", "Cellulant", "https://linkedin.com/in/ben-sang-6295a021"),
    ("Kelvin Njoroge", "Data Engineer", "Kenya Airways", "https://linkedin.com/in/kelvin-karori"),
    ("Caleb Kilemba", "Data Engineer", "Data Science East Africa", "https://linkedin.com/in/caleb-kilemba"),
    ("David Mwandairo", "Data Engineer", "Data Science East Africa", "https://linkedin.com/in/david-mwandairo-068aa53bb"),
    ("Denzel Kinyua", "Data Engineer (Spark, Kafka)", "Data Science East Africa / Upwork", "https://linkedin.com/in/denzel-kinyua-a73597277"),
    ("Dennis Maingi", "Senior Data Engineer", "DATASEAL Software Ltd", "https://linkedin.com/in/dennis-maingi-1b207417a"),
    ("Ronald Nyagaka", "Data Engineer", "Singlet", "https://linkedin.com/in/ronald-nyagaka"),
    ("Otieno Oduor", "Data Engineer", "Uwezo Fund Oversight Board", "https://linkedin.com/in/otieno-oduor-a7b384226"),
    ("Tapiwanashe Mlangeni", "Senior Data Engineer & Architect", "Freelance", "https://linkedin.com/in/tamla83"),
    ("Martin Wanjiru", "Data Engineer", "Deel", "https://linkedin.com/in/martin-wanjiru-98414111a"),
    ("Stephen Waigi", "Data Engineer / Cloud Architect", "Andela", "https://linkedin.com/in/stephen-waigi-4a5ba1275"),
    ("Muyukani Kizito", "Data Engineer (dbt, GCP, AWS)", "ThrottleUp Technologies (US remote)", "https://linkedin.com/in/muyukani-kizito"),
    ("Kevin N.", "Solutions Architect / Snr Data Engineer", "Network International", "https://linkedin.com/in/kevinndungu985"),
    ("Kennedy Wambua", "Data Engineer", "NCBA Group", "https://linkedin.com/in/kennedywambua"),
    ("Joyce Mwega", "Data Engineer", "KCB Bank Group", "https://linkedin.com/in/joyce-mwega-8688a7122"),
    ("Dennis Maiyo", "Data Engineer", "Sanku", "https://linkedin.com/in/dennis-maiyo-69945611a"),
    ("MaryJoy Kinyua", "Data Engineer, BI & Analytics", "APA Insurance", "https://linkedin.com/in/maryjoy-kinyua"),
    ("Dancun Koech", "Data Engineer", "NAB / Airtel Africa", "https://linkedin.com/in/dancun-koech-4a643a308"),
    ("Ian Daniel Mathenge", "Data Engineer / Analytics Engineer", "e-MPS", "https://linkedin.com/in/iandanielmathenge"),
    ("Vincent Kiti", "Data Engineer (ETL, Airflow)", "Reliance Infosystems", "https://linkedin.com/in/vincent-kiti-3b7b69218"),
    ("Eric Gachomba", "Data Engineer", "ArtSam Data Technologies", "https://linkedin.com/in/eric-gachomba-82546b136"),
    ("Emmanuel Sitienei", "Data Engineer (Fabric DP-600/700)", "Independent / consulting", "https://linkedin.com/in/emmanuelsitienei"),
]

PIPELINES = [
    ("Andela", "https://www.andela.com/careers", "Places African engineers into global remote roles."),
    ("Turing", "https://www.turing.com/jobs", "Vetted remote data/software roles with US companies."),
    ("Toptal", "https://www.toptal.com/talent/apply", "Elite freelance network; data engineering vertical."),
    ("Crossover", "https://www.crossover.com/jobs", "Full-time remote roles; rigorous testing."),
    ("Deel", "https://www.deel.com/careers", "Remote-first company hiring data/engineering."),
    ("Astronomer", "https://www.astronomer.io/careers", "The Apache Airflow company."),
    ("dbt Labs", "https://getdbt.com/dbt-labs/open-roles", "Watch for EMEA openings."),
    ("Databricks", "https://www.databricks.com/company/careers", "Field/solutions engineering and data roles."),
    ("Snowflake", "https://careers.snowflake.com", "Solutions/data engineering roles."),
    ("GitLab", "https://about.gitlab.com/jobs", "All-remote company."),
    ("Himalayas", "https://himalayas.app/jobs/data-engineer", "Remote data jobs with location filters."),
    ("Remotive", "https://remotive.com/remote-jobs/data", "Curated remote data jobs."),
    ("Matcha", "https://matcha.fm/jobs/data-engineer/ww", "Startup data roles open worldwide."),
    ("OpenToAfrica", "https://opentoafrica.com", "Africa-friendly remote roles."),
    ("PySpark.in", "https://pyspark.in/jobs/", "Live Spark/data roles refreshed daily."),
    ("DailyRemote", "https://dailyremote.com/remote-data-engineer-jobs", "1,200+ remote data-engineer jobs."),
    ("BrighterMonday", "https://www.brightermonday.co.ke/jobs/software-data/nairobi/full-time", "Largest Kenyan job board."),
    ("MyJobMag Kenya", "https://www.myjobmag.co.ke", "Daily Kenyan vacancies."),
    ("Fuzu Kenya", "https://www.fuzu.com/kenya", "Kenya/East Africa roles."),
    ("Corporate Staffing", "https://www.corporatestaffing.co.ke/category/it-jobs-in-kenya/", "Recruiter-run Kenyan IT listings."),
    ("AjiraHub", "https://www.ajirahub.co.ke", "Kenyan tech/data aggregator."),
    ("LinkedIn Jobs", "https://www.linkedin.com/jobs", "Alerts: Data Engineer Kenya; Databricks worldwide."),
]

CSS = """
:root{--bg:#f4f6fb;--card:#fff;--ink:#111827;--muted:#6b7280;--line:#e5e7eb;--brand:#0f766e;--brand-dark:#134e4a;--green:#15803d;--green-bg:#dcfce7;--amber:#b45309;--amber-bg:#fef3c7;--blue:#1d4ed8;--blue-bg:#dbeafe;--purple:#6d28d9;--purple-bg:#ede9fe;--red:#b91c1c;--red-bg:#fee2e2;--shadow:0 1px 2px rgba(16,24,40,.06),0 8px 24px rgba(16,24,40,.06)}
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;background:var(--bg);color:var(--ink);line-height:1.5}
a{color:var(--brand);text-decoration:none}a:hover{text-decoration:underline}
.hero{background:radial-gradient(1200px 400px at 20% -10%,#1e3a8a 0%,transparent 60%),linear-gradient(135deg,#0b1220 0%,#0f2a3a 55%,#134e4a 100%);color:#fff;padding:40px 24px 30px}
.wrap{max-width:1180px;margin:0 auto}.eyebrow{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#99f6e4;font-weight:700}
.hero h1{font-size:clamp(26px,4vw,40px);margin:10px 0 6px;line-height:1.1}.hero h1 span{color:#5eead4}
.hero p{color:#cbd5e1;max-width:820px;font-size:15px;margin:0}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:-22px auto 0;position:relative;z-index:2}
.stat{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:15px 17px;box-shadow:var(--shadow)}
.stat .n{font-size:25px;font-weight:800}.stat .l{font-size:12px;color:var(--muted)}
main{padding:30px 24px 50px}section{margin-top:32px}
h2{font-size:22px;margin:0 0 4px;letter-spacing:-.02em}.sub{color:var(--muted);font-size:13.5px;margin:0 0 14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:15px;padding:16px;box-shadow:var(--shadow);display:flex;flex-direction:column}
.co{font-size:11.5px;color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:.06em}
.role{font-size:15.5px;font-weight:800;margin:2px 0 0;line-height:1.25}
.badges{display:flex;flex-wrap:wrap;gap:6px;margin:9px 0 0}
.badge{font-size:10.5px;font-weight:700;padding:3px 8px;border-radius:999px;white-space:nowrap}
.b-remote{background:var(--green-bg);color:var(--green)}.b-world{background:var(--purple-bg);color:var(--purple)}
.b-onsite{background:var(--blue-bg);color:var(--blue)}.b-hybrid{background:var(--amber-bg);color:var(--amber)}
.b-salary{background:#e0f2fe;color:#075985}.b-urgent{background:var(--red-bg);color:var(--red)}
.b-watch{background:#f3f4f6;color:#4b5563}
.meta{margin:9px 0 0;font-size:12px;color:var(--muted);display:grid;gap:3px}.meta b{color:#374151}
.match{margin:12px 0 0}.match-row{display:flex;justify-content:space-between;font-size:10.5px;color:var(--muted);font-weight:700;text-transform:uppercase}
.bar{height:7px;background:#eef2f7;border-radius:999px;margin-top:5px;overflow:hidden}
.bar>i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#0f766e,#2dd4bf)}
.tags{display:flex;flex-wrap:wrap;gap:5px;margin:10px 0 0}
.tag{font-size:10.5px;background:#f1f5f9;color:#334155;border:1px solid #e2e8f0;border-radius:6px;padding:2px 7px}
.foot{margin-top:auto;padding-top:12px}.apply{display:inline-flex;background:var(--brand-dark);color:#fff;font-weight:700;font-size:12.5px;padding:7px 12px;border-radius:8px}
.apply:hover{background:var(--brand);text-decoration:none}
.note{background:#fff;border:1px solid var(--line);border-left:4px solid var(--brand);border-radius:12px;padding:13px 15px;font-size:13px;color:#374151;margin:14px 0 0}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:12px;overflow:hidden;box-shadow:var(--shadow)}
th,td{text-align:left;padding:9px 11px;font-size:12.5px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:#f8fafc;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#475569}
tr:last-child td{border-bottom:0}.small{color:var(--muted);font-size:11px}
.pipes{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px}
.pipe{background:#fff;border:1px solid var(--line);border-radius:11px;padding:11px 13px;box-shadow:var(--shadow)}
.pipe a{font-weight:700;font-size:13px}.pipe p{margin:3px 0 0;font-size:12px;color:var(--muted)}
details summary{cursor:pointer;color:var(--brand);font-weight:700;font-size:13.5px;margin-bottom:10px}
footer{border-top:1px solid var(--line);background:#fff;padding:20px 24px;color:var(--muted);font-size:12px}
@media print{.hero{background:#0b1220}.card,table,.pipe{box-shadow:none;break-inside:avoid}}
"""


def esc(value):
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def setup_logging():
    LOGS_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOGS_DIR / "daily_jobs.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def load_config(path=None):
    path = Path(path) if path else ROOT / "config.json"
    if not path.exists():
        example = ROOT / "config.example.json"
        if example.exists():
            logging.warning("config.json missing - using config.example.json (email disabled)")
            path = example
        else:
            return {"email": {"enabled": False}, "run": {}}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def http_json(url):
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def http_text(url):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")


def normalize_location(location):
    return re.sub(r"\s+", " ", (location or "").strip())


def is_eligible(location):
    loc = normalize_location(location).lower()
    if not loc:
        return True
    if re.search(r"\b(us|usa|u\.s\.|united states|canada|north america|americas)\b", loc):
        return False
    if any(token in loc for token in RESTRICTED_TOKENS):
        return any(token in loc for token in ["worldwide", "anywhere", "global", "africa", "kenya", "emea"])
    return any(token in loc for token in ELIGIBLE_TOKENS)


def clean_description(raw):
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def score_job(title, description, tags):
    text = " ".join([title or "", description or "", " ".join(tags or [])]).lower()
    hits = sum(1 for skill in CV_SKILLS if skill in text)
    value = 50 + hits * 3
    if is_relevant(title):
        value += 10
    if any(keyword in (title or "").lower() for keyword in TITLE_KEYWORDS):
        value += 8
    return min(98, value)


def dedupe(jobs):
    seen = set()
    result = []
    for job in jobs:
        key = job_key(job)
        if key and key not in seen:
            seen.add(key)
            result.append(job)
    return result


def job_key(job):
    return re.sub(r"[^a-z0-9]+", "", (job.get("title", "") + job.get("company", "")).lower())


def load_tracking():
    if not TRACKING_PATH.exists():
        return {"jobs": {}}
    try:
        data = json.loads(TRACKING_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logging.warning("tracking.json unreadable: %s", exc)
        return {"jobs": {}}
    if not isinstance(data.get("jobs"), dict):
        data["jobs"] = {}
    return data


def save_tracking(tracking):
    TRACKING_PATH.write_text(
        json.dumps(tracking, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def mark_jobs(tracking, remote_jobs, kenya_jobs, status="applied"):
    today = datetime.now().strftime("%Y-%m-%d")
    marked = 0
    for category, collection in (("remote", remote_jobs), ("kenya", kenya_jobs)):
        for job in collection:
            key = job_key(job)
            if not key:
                continue
            entry = tracking["jobs"].get(key)
            if entry and entry.get("status") == status:
                continue
            tracking["jobs"][key] = {
                "company": job.get("company", ""),
                "title": job.get("title", ""),
                "url": job.get("url", ""),
                "location": job.get("location", ""),
                "category": category,
                "status": status,
                "marked": today,
            }
            marked += 1
    return marked


def split_tracked(remote_jobs, kenya_jobs, tracking):
    tracked = tracking.get("jobs", {})
    fresh_remote = [job for job in remote_jobs if job_key(job) not in tracked]
    fresh_kenya = [job for job in kenya_jobs if job_key(job) not in tracked]
    return fresh_remote, fresh_kenya


def is_relevant(title):
    text = (title or "").lower()
    if any(token in text for token in EXCLUDE_TITLE_TOKENS):
        return False
    if any(token in text for token in RELEVANT_TITLE_TOKENS):
        return True
    return bool(re.search(r"\bdata\b", text)) and ("engineer" in text or "platform" in text)


def fetch_remotive():
    data = http_json("https://remotive.com/api/remote-jobs?category=data&limit=100")
    jobs = []
    for item in data.get("jobs", []):
        location = item.get("candidate_required_location", "")
        if not is_eligible(location):
            continue
        description = clean_description(item.get("description", ""))
        jobs.append({
            "title": item.get("title", ""),
            "company": item.get("company_name", ""),
            "location": location or "Remote",
            "url": item.get("url", ""),
            "source": "Remotive",
            "tags": item.get("tags", [])[:6],
            "salary": item.get("salary", "") or "",
            "date": (item.get("publication_date", "") or "")[:10],
            "score": score_job(item.get("title", ""), description, item.get("tags", [])),
        })
    logging.info("Remotive: %s eligible jobs", len(jobs))
    return jobs


def fetch_remoteok():
    data = http_json("https://remoteok.com/api")
    jobs = []
    for item in data:
        if not isinstance(item, dict) or not item.get("position"):
            continue
        location = item.get("location", "")
        if not is_eligible(location):
            continue
        tags = item.get("tags", [])
        title = item.get("position", "")
        description = clean_description(item.get("description", ""))
        salary = ""
        if item.get("salary_min") or item.get("salary_max"):
            salary = f"${item.get('salary_min', 0):,}-${item.get('salary_max', 0):,}"
        raw_date = item.get("date")
        if isinstance(raw_date, (int, float)):
            date_str = datetime.fromtimestamp(raw_date).strftime("%Y-%m-%d")
        elif isinstance(raw_date, str):
            date_str = raw_date[:10]
        else:
            date_str = ""
        jobs.append({
            "title": title,
            "company": item.get("company", ""),
            "location": location or "Remote",
            "url": item.get("url", ""),
            "source": "RemoteOK",
            "tags": tags[:6],
            "salary": salary,
            "date": date_str,
            "score": score_job(title, description, tags),
        })
    logging.info("RemoteOK: %s eligible jobs", len(jobs))
    return jobs


def fetch_jobicy():
    data = http_json("https://jobicy.com/api/v2/remote-jobs?count=50&industry=data-science")
    jobs = []
    for item in data.get("jobs", []):
        geo = item.get("jobGeo", "")
        if isinstance(geo, list):
            geo = ", ".join(str(value) for value in geo)
        location = geo
        if not is_eligible(location):
            continue
        title = item.get("jobTitle", "")
        industry = item.get("jobIndustry")
        if isinstance(industry, list):
            tags = [str(value) for value in industry if value]
        elif industry:
            tags = [str(industry)]
        else:
            tags = []
        description = clean_description(item.get("jobExcerpt", ""))
        salary = ""
        if item.get("annualSalaryMin"):
            salary = f"{item.get('salaryCurrency', '$')}{item.get('annualSalaryMin')}-{item.get('annualSalaryMax', '')}"
        jobs.append({
            "title": title,
            "company": item.get("companyName", ""),
            "location": location or "Remote",
            "url": item.get("url", ""),
            "source": "Jobicy",
            "tags": tags[:6],
            "salary": salary,
            "date": (item.get("pubDate", "") or "")[:10],
            "score": score_job(title, description, tags),
        })
    logging.info("Jobicy: %s eligible jobs", len(jobs))
    return jobs


def fetch_arbeitnow():
    data = http_json("https://www.arbeitnow.com/api/job-board-api")
    jobs = []
    for item in data.get("data", []):
        if not item.get("remote"):
            continue
        location = item.get("location", "")
        if not is_eligible(location):
            continue
        title = item.get("title", "")
        tags = item.get("tags", [])
        description = clean_description(item.get("description", ""))
        jobs.append({
            "title": title,
            "company": item.get("company_name", ""),
            "location": location or "Remote",
            "url": item.get("url", ""),
            "source": "Arbeitnow",
            "tags": tags[:6],
            "salary": "",
            "date": datetime.fromtimestamp(item["created_at"]).strftime("%Y-%m-%d") if item.get("created_at") else "",
            "score": score_job(title, description, tags),
        })
    logging.info("Arbeitnow: %s eligible jobs", len(jobs))
    return jobs


def fetch_wwr():
    xml = http_text("https://weworkremotely.com/categories/remote-programming-jobs.rss")
    root = ET.fromstring(xml)
    jobs = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        region = (item.findtext("region") or "").strip()
        if not is_eligible(region):
            continue
        company, _, role = title.partition(":")
        role = role.strip() or title
        link = (item.findtext("link") or "").strip()
        description = clean_description(item.findtext("description") or "")
        tags = [category.text for category in item.findall("category") if category.text]
        jobs.append({
            "title": role,
            "company": company.strip(),
            "location": region or "Remote",
            "url": link,
            "source": "WeWorkRemotely",
            "tags": tags[:6],
            "salary": "",
            "date": (item.findtext("pubDate") or "")[:16],
            "score": score_job(role, description, tags),
        })
    logging.info("WeWorkRemotely: %s eligible jobs", len(jobs))
    return jobs


def fetch_myjobmag():
    url = "https://www.myjobmag.co.ke/jobs-by-title/data-engineer"
    html_text = http_text(url)
    jobs = []
    pattern = re.compile(
        r'<h2><a href="(?P<path>/job/[^"]+)"[^>]*>(?P<title>[^<]{3,160})</a></h2>',
        re.IGNORECASE,
    )
    for match in pattern.finditer(html_text):
        raw_title = match.group("title").strip()
        if "data engineer" not in raw_title.lower():
            continue
        if " at " in raw_title:
            role, company = raw_title.rsplit(" at ", 1)
        else:
            role, company = raw_title, "MyJobMag listing"
        jobs.append({
            "category": "kenya",
            "company": company.strip(),
            "title": role.strip(),
            "location": "Kenya",
            "type": "Verify (onsite/remote)",
            "deadline": "See listing",
            "stack": "See listing",
            "url": "https://www.myjobmag.co.ke" + match.group("path"),
            "note": "Live MyJobMag data-engineer listing.",
            "source": "MyJobMag",
        })
    logging.info("MyJobMag: %s data-engineer listings", len(jobs))
    return jobs


ASHBY_NAMES = {
    "people-data-labs": "People Data Labs",
    "oyster": "Oyster",
    "revenuebase-inc": "RevenueBase",
    "supabase": "Supabase",
    "notion": "Notion",
    "zapier": "Zapier",
}

GREENHOUSE_NAMES = {
    "canonical": "Canonical (Ubuntu)",
    "gitlab": "GitLab",
    "elastic": "Elastic",
    "fivetran": "Fivetran",
    "mongodb": "MongoDB",
    "moniepoint": "Moniepoint",
    "stripe": "Stripe",
    "datadog": "Datadog",
}


def fetch_ashby(org):
    data = http_json(f"https://api.ashbyhq.com/posting-api/job-board/{org}")
    jobs = []
    for item in data.get("jobs", []):
        if not item.get("isListed", True):
            continue
        title = item.get("title", "")
        location = item.get("location", "")
        secondary = item.get("secondaryLocations") or []
        secondary_text = ", ".join(
            value.get("location", "") for value in secondary if isinstance(value, dict)
        )
        location_text = ", ".join(part for part in [location, secondary_text] if part)
        if not is_eligible(location_text):
            continue
        description = clean_description(item.get("descriptionHtml", ""))
        jobs.append({
            "title": title,
            "company": ASHBY_NAMES.get(org, org.replace("-", " ").title()),
            "location": location_text or "Remote",
            "url": item.get("jobUrl", ""),
            "source": f"Ashby ({org})",
            "tags": [item.get("department", "")] if item.get("department") else [],
            "salary": "",
            "date": (item.get("publishedAt", "") or "")[:10],
            "score": score_job(title, description, []),
        })
    logging.info("Ashby %s: %s eligible jobs", org, len(jobs))
    return jobs


def fetch_greenhouse(token):
    data = http_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true")
    jobs = []
    for item in data.get("jobs", []):
        title = item.get("title", "")
        location = (item.get("location") or {}).get("name", "")
        if not is_eligible(location):
            continue
        description = clean_description(item.get("content", ""))
        jobs.append({
            "title": title,
            "company": GREENHOUSE_NAMES.get(token, token.title()),
            "location": location or "Remote",
            "url": item.get("absolute_url", ""),
            "source": f"Greenhouse ({token})",
            "tags": [],
            "salary": "",
            "date": (item.get("updated_at", "") or "")[:10],
            "score": score_job(title, description, []),
        })
    logging.info("Greenhouse %s: %s eligible jobs", token, len(jobs))
    return jobs


def fetch_lever(token):
    data = http_json(f"https://api.lever.co/v0/postings/{token}?mode=json")
    jobs = []
    for item in data:
        title = item.get("text", "")
        categories = item.get("categories") or {}
        location = categories.get("location", "")
        if not is_eligible(location):
            continue
        jobs.append({
            "title": title,
            "company": token.title(),
            "location": location or "Remote",
            "url": item.get("hostedUrl", ""),
            "source": f"Lever ({token})",
            "tags": [categories.get("team", "")] if categories.get("team") else [],
            "salary": "",
            "date": datetime.fromtimestamp(item["createdAt"] / 1000).strftime("%Y-%m-%d") if item.get("createdAt") else "",
            "score": score_job(title, clean_description(item.get("descriptionPlain", "")), []),
        })
    logging.info("Lever %s: %s eligible jobs", token, len(jobs))
    return jobs


def fetch_all(config):
    remote_jobs = []
    kenya_jobs = []
    companies = config.get("companies", {})
    sources = [
        ("remotive", fetch_remotive),
        ("remoteok", fetch_remoteok),
        ("jobicy", fetch_jobicy),
        ("arbeitnow", fetch_arbeitnow),
        ("wwr", fetch_wwr),
        ("myjobmag", fetch_myjobmag),
    ]
    for org in companies.get("ashby", []):
        sources.append((f"ashby:{org}", lambda org=org: fetch_ashby(org)))
    for token in companies.get("greenhouse", []):
        sources.append((f"greenhouse:{token}", lambda token=token: fetch_greenhouse(token)))
    for token in companies.get("lever", []):
        sources.append((f"lever:{token}", lambda token=token: fetch_lever(token)))
    for name, fetcher in sources:
        try:
            fetched = fetcher()
        except Exception as exc:
            logging.warning("%s failed: %s", name, exc)
            continue
        for job in fetched:
            if job.get("category") == "kenya":
                kenya_jobs.append(job)
            elif is_relevant(job["title"]):
                remote_jobs.append(job)
    remote_jobs = dedupe(remote_jobs)
    remote_jobs.sort(key=lambda job: (job["score"], job["date"]), reverse=True)
    kenya_jobs = dedupe(kenya_jobs)
    return remote_jobs, kenya_jobs


def merge_kenya(curated, scraped):
    merged = list(curated)
    seen = {job_key(job) for job in curated}
    for job in scraped:
        key = job_key(job)
        if key not in seen:
            seen.add(key)
            merged.append(job)
    return merged


def render_remote_card(job):
    badges = [f'<span class="badge b-remote">Remote</span>']
    location = job["location"]
    if any(token in location.lower() for token in ["worldwide", "anywhere", "global", "africa", "kenya", "emea"]):
        badges.append(f'<span class="badge b-world">{esc(location)}</span>')
    else:
        badges.append(f'<span class="badge b-watch">{esc(location)}</span>')
    if job["salary"]:
        badges.append(f'<span class="badge b-salary">{esc(job["salary"])}</span>')
    tags = "".join(f'<span class="tag">{esc(tag)}</span>' for tag in job["tags"] if tag)
    return f"""
    <article class="card">
      <div class="co">{esc(job['company'])}</div>
      <h3 class="role">{esc(job['title'])}</h3>
      <div class="badges">{''.join(badges)}</div>
      <div class="meta"><span><b>Source:</b> {esc(job['source'])}</span><span><b>Posted:</b> {esc(job['date'] or 'recent')}</span></div>
      <div class="match"><div class="match-row"><span>CV match</span><span>{job['score']}%</span></div><div class="bar"><i style="width:{job['score']}%"></i></div></div>
      <div class="tags">{tags}</div>
      <div class="foot"><a class="apply" href="{esc(job['url'])}" target="_blank" rel="noopener">View &amp; apply</a></div>
    </article>"""


def render_kenya_card(job):
    type_class = "b-remote" if job["type"].lower().startswith("remote") else "b-hybrid" if job["type"].lower().startswith("hybrid") else "b-onsite"
    return f"""
    <article class="card">
      <div class="co">{esc(job['company'])}</div>
      <h3 class="role">{esc(job['title'])}</h3>
      <div class="badges">
        <span class="badge {type_class}">{esc(job['type'])} — {esc(job['location'])}</span>
        <span class="badge b-urgent">{esc(job['deadline'])}</span>
      </div>
      <div class="meta"><span><b>Stack:</b> {esc(job['stack'])}</span><span><b>Note:</b> {esc(job['note'])}</span></div>
      <div class="foot"><a class="apply" href="{esc(job['url'])}" target="_blank" rel="noopener">View &amp; apply</a></div>
    </article>"""


def render_tracked_table(entries):
    if not entries:
        return '<p class="small">No reviewed or applied jobs recorded yet.</p>'
    rows = "".join(
        f'<tr><td><a href="{esc(entry.get("url", ""))}" target="_blank" rel="noopener">{esc(entry.get("company", ""))}</a></td>'
        f'<td>{esc(entry.get("title", ""))}</td>'
        f'<td>{esc(entry.get("location", ""))}</td>'
        f'<td><span class="badge b-watch">{esc(str(entry.get("status", "")).title())}</span></td>'
        f'<td class="small">{esc(entry.get("marked", ""))}</td></tr>'
        for entry in sorted(
            entries,
            key=lambda item: (item.get("marked", ""), item.get("company", "")),
            reverse=True,
        )
    )
    return (
        "<table><thead><tr><th>Company</th><th>Role</th><th>Location</th>"
        f"<th>Status</th><th>Marked</th></tr></thead><tbody>{rows}</tbody></table>"
    )


def render_html(jobs, kenya_jobs, tracked_entries=None):
    tracked_entries = tracked_entries or []
    now = datetime.now()
    today = now.strftime("%d %B %Y")
    people_rows = "".join(
        f'<tr><td><a href="{esc(url)}" target="_blank" rel="noopener">{esc(name)}</a></td><td>{esc(role)}</td><td>{esc(company)}</td></tr>'
        for name, role, company, url in PEOPLE
    )
    pipe_cards = "".join(
        f'<div class="pipe"><a href="{esc(url)}" target="_blank" rel="noopener">{esc(name)}</a><p>{esc(desc)}</p></div>'
        for name, url, desc in PIPELINES
    )
    remote_cards = "".join(render_remote_card(job) for job in jobs)
    kenya_cards = "".join(render_kenya_card(job) for job in kenya_jobs)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Daily Data Engineering Job Report — {today}</title>
<style>{CSS}</style>
</head>
<body>
<header class="hero">
  <div class="wrap">
    <div class="eyebrow">Daily report · generated {today}</div>
    <h1>Evans Langat — <span>Data Engineer</span> jobs</h1>
    <p>Auto-generated from Remotive, RemoteOK, Jobicy, Arbeitnow, WeWorkRemotely and MyJobMag, plus curated Kenya roles and the LinkedIn map. Remote roles are filtered for worldwide / Africa / Kenya / EMEA eligibility. Verify every listing before applying.</p>
  </div>
</header>
<div class="wrap">
  <div class="stats">
    <div class="stat"><div class="n">{len(jobs)}</div><div class="l">Remote / eligible roles today</div></div>
    <div class="stat"><div class="n">{len(kenya_jobs)}</div><div class="l">Kenya roles tracked</div></div>
    <div class="stat"><div class="n">{len(tracked_entries)}</div><div class="l">Reviewed / applied (remembered)</div></div>
    <div class="stat"><div class="n">{len(PEOPLE)}</div><div class="l">Kenyan data engineers mapped</div></div>
    <div class="stat"><div class="n">{len(PIPELINES)}</div><div class="l">Always-on job boards</div></div>
  </div>
</div>
<main class="wrap">
  <section>
    <h2>Remote — worldwide / Kenya-eligible</h2>
    <p class="sub">Fetched {now.strftime('%H:%M')} on {today}. Sorted by CV match. Confirm country eligibility on the application page.</p>
    <div class="grid">{remote_cards}</div>
  </section>
  <section>
    <h2>Kenya — remote, hybrid &amp; onsite</h2>
    <p class="sub">Curated and verified manually; deadlines change — confirm on the employer page.</p>
    <div class="grid">{kenya_cards}</div>
  </section>
  <section>
    <h2>Reviewed &amp; applied — remembered</h2>
    <p class="sub">These roles are kept out of the fresh lists above so you don't re-review them. Stored in tracking.json.</p>
    <details><summary>Show {len(tracked_entries)} remembered roles</summary>{render_tracked_table(tracked_entries)}</details>
  </section>
  <section>
    <h2>LinkedIn map — Kenyan data engineers</h2>
    <p class="sub">Use for warm referrals. Connect with a short note and ask about the team, not for a job link.</p>
    <table><thead><tr><th>Person</th><th>Role</th><th>Company</th></tr></thead><tbody>{people_rows}</tbody></table>
  </section>
  <section>
    <h2>Always-on pipelines &amp; job boards</h2>
    <div class="pipes">{pipe_cards}</div>
  </section>
  <section>
    <div class="note"><b>Today's priority:</b> apply to the top 3 remote matches, then the earliest Kenya deadline. Keep one tailored CV per role family: Databricks/PySpark, dbt/Snowflake, and analytics engineering.</div>
  </section>
</main>
<footer><div class="wrap">Generated automatically by daily_jobs.py · evanslangat22@gmail.com · +254 705 719 262</div></footer>
</body>
</html>"""


def send_email(html_text, subject, config):
    email_cfg = config.get("email", {})
    if not email_cfg.get("enabled"):
        logging.info("Email disabled in config - report saved only")
        return False
    required = ["smtp_host", "username", "password", "from", "to"]
    missing = [key for key in required if not email_cfg.get(key)]
    if missing:
        logging.error("Email config missing: %s", ", ".join(missing))
        return False
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = email_cfg["from"]
    message["To"] = ", ".join(email_cfg["to"])
    message.set_content("Your daily data engineering job report is attached as HTML.")
    message.add_alternative(html_text, subtype="html")
    host = email_cfg["smtp_host"]
    port = int(email_cfg.get("smtp_port", 587))
    password = email_cfg["password"].replace(" ", "")
    if email_cfg.get("use_ssl"):
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=30) as server:
            server.login(email_cfg["username"], password)
            server.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(email_cfg["username"], password)
            server.send_message(message)
    logging.info("Email sent to %s", ", ".join(email_cfg["to"]))
    return True


def main():
    parser = argparse.ArgumentParser(description="Fetch data engineering jobs and email an HTML report")
    parser.add_argument("--config", help="Path to config.json")
    parser.add_argument("--no-email", action="store_true", help="Skip sending email")
    parser.add_argument("--min-score", type=int, help="Override minimum CV match score")
    parser.add_argument(
        "--mark-applied",
        action="store_true",
        help="Mark all jobs in this run as applied and remember them in tracking.json",
    )
    args = parser.parse_args()

    setup_logging()
    config = load_config(args.config)
    run_cfg = config.get("run", {})
    min_score = args.min_score or int(run_cfg.get("min_match_score", 55))
    max_jobs = int(run_cfg.get("max_remote_jobs", 40))

    logging.info("Starting daily job report")
    tracking = load_tracking()
    jobs, scraped_kenya = fetch_all(config)
    jobs = [job for job in jobs if job["score"] >= min_score]
    kenya_jobs = merge_kenya(KENYA_JOBS, scraped_kenya)
    if args.mark_applied:
        marked = mark_jobs(tracking, jobs, kenya_jobs)
        save_tracking(tracking)
        logging.info("Marked %s jobs as applied in %s", marked, TRACKING_PATH)
    jobs, kenya_jobs = split_tracked(jobs, kenya_jobs, tracking)
    jobs = jobs[:max_jobs]
    tracked_entries = list(tracking.get("jobs", {}).values())
    logging.info(
        "Selected %s remote jobs and %s Kenya jobs (min score %s); %s remembered",
        len(jobs), len(kenya_jobs), min_score, len(tracked_entries),
    )

    html_text = render_html(jobs, kenya_jobs, tracked_entries)
    REPORTS_DIR.mkdir(exist_ok=True)
    dated_path = REPORTS_DIR / f"jobs-{datetime.now().strftime('%Y-%m-%d')}.html"
    latest_path = REPORTS_DIR / "latest.html"
    dated_path.write_text(html_text, encoding="utf-8")
    latest_path.write_text(html_text, encoding="utf-8")
    logging.info("Report written to %s", dated_path)

    if not args.no_email:
        try:
            send_email(html_text, f"Daily Data Engineering Jobs — {datetime.now().strftime('%d %b %Y')}", config)
        except Exception as exc:
            logging.error("Email failed: %s", exc)
    logging.info("Done")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    raise SystemExit(main())
