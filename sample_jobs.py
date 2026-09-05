"""Sample job listings used by --demo and by the self test.

These are hand written stand ins for Upwork search results, including a few
deliberately off topic listings so the demotion rules can be seen working.
Nothing here touches the network.
"""

# keywords: which searches this listing shows up under. A listing under two
# keywords also exercises the dedupe path.
SAMPLE_JOBS = [
    dict(
        id="021968676050348026869",
        title="Build a Python web scraper for e-commerce product data",
        keywords=["web scraping", "data scraper"],
        posted="2 hours ago",
        type="Hourly: $15.00 - $30.00",
        budget="",
        proposals="Less than 5",
        location="United States",
        skills=["Web Scraping", "Python", "Data Extraction", "Scrapy", "BeautifulSoup"],
        description=("We need a scraper that pulls product titles, prices and stock "
                     "levels from 3 competitor sites daily and writes them to CSV. "
                     "Must handle pagination and basic anti-bot protection."),
    ),
    dict(
        id="021968676050348026870",
        title="Data scraper needed for real estate listings (ongoing)",
        keywords=["data scraper"],
        posted="yesterday",
        type="Fixed price",
        budget="Est. Budget: $300.00",
        proposals="5 to 10",
        location="Canada",
        skills=["Data Scraping", "Python", "Automation", "API"],
        description=("Looking for a developer to build a crawler that collects new "
                     "property listings from several regional portals and exports "
                     "them into a Google Sheet every morning."),
    ),
    dict(
        id="021968676050348026871",
        title="Scrape NFT marketplace data into a blockchain dashboard",
        keywords=["web scraping"],
        posted="3 hours ago",
        type="Hourly: $20.00 - $45.00",
        budget="",
        proposals="10 to 15",
        location="Singapore",
        skills=["Blockchain", "Web3", "Web Scraping", "Solidity"],
        description=("Scrape NFT floor prices across web3 marketplaces and feed a "
                     "crypto analytics dashboard. Experience with smart contract "
                     "events required."),
    ),
    dict(
        id="021968676050348026872",
        title="LinkedIn lead scraping bot with CSV export",
        keywords=["web scraping"],
        posted="4 days ago",
        type="Fixed price",
        budget="Est. Budget: $150.00",
        proposals="20 to 50",
        location="United Kingdom",
        skills=["Web Scraping", "Lead Generation", "Python", "Selenium"],
        description=("Need a bot that collects public profile data for a target "
                     "industry and exports clean CSV files. Proxy rotation and "
                     "captcha handling a plus."),
    ),
    dict(
        id="021968676050348026873",
        title="Google Sheets automation with Apps Script for inventory tracking",
        keywords=["google sheets automation", "google apps script"],
        posted="5 hours ago",
        type="Hourly: $18.00 - $35.00",
        budget="",
        proposals="Less than 5",
        location="Australia",
        skills=["Google Apps Script", "Google Sheets", "Automation", "JavaScript"],
        description=("We track stock across three warehouses in Google Sheets. We "
                     "want Apps Script automation that consolidates the tabs, emails "
                     "a daily summary and flags low stock rows."),
    ),
    dict(
        id="021968676050348026874",
        title="Custom function in Google Apps Script to sync Sheets with our CRM",
        keywords=["google apps script"],
        posted="yesterday",
        type="Fixed price",
        budget="Est. Budget: $400.00",
        proposals="5 to 10",
        location="Germany",
        skills=["Google Apps Script", "Google Workspace", "API", "Integration"],
        description=("Build a custom function and time driven trigger that pushes new "
                     "Google Sheets rows into our CRM through its REST API, with "
                     "error logging back into the sheet."),
    ),
    dict(
        id="021968676050348026875",
        title="Automate weekly reporting in Google Sheets",
        keywords=["google sheets automation"],
        posted="2 days ago",
        type="Fixed price",
        budget="Est. Budget: $90.00",
        proposals="15 to 20",
        location="United States",
        skills=["Google Sheets", "Automation", "Zapier", "Dashboard"],
        description=("Weekly sales numbers arrive as CSV. We want them appended to a "
                     "master sheet automatically and a summary dashboard tab that "
                     "refreshes itself."),
    ),
    dict(
        id="021968676050348026876",
        title="Excel dashboard with pivot tables and dynamic charts",
        keywords=["excel dashboard"],
        posted="1 hour ago",
        type="Fixed price",
        budget="Est. Budget: $250.00",
        proposals="Less than 5",
        location="United Arab Emirates",
        skills=["Microsoft Excel", "Pivot Tables", "Dashboard", "Power Query"],
        description=("Turn our monthly sales export into an interactive Excel "
                     "dashboard with slicers, pivot tables and charts that update "
                     "when new data is pasted in."),
    ),
    dict(
        id="021968676050348026877",
        title="Excel VBA macro to clean and merge messy data files",
        keywords=["excel automation"],
        posted="6 hours ago",
        type="Hourly: $12.00 - $25.00",
        budget="",
        proposals="5 to 10",
        location="United States",
        skills=["Excel VBA", "Macro", "Data Cleaning", "Microsoft Excel"],
        description=("We receive 30 spreadsheets a week in inconsistent formats. Need "
                     "a VBA macro that standardises headers, removes duplicates and "
                     "merges everything into one workbook."),
    ),
    dict(
        id="021968676050348026878",
        title="Excel formulas help for financial model",
        keywords=["excel automation", "excel dashboard"],
        posted="3 days ago",
        type="Fixed price",
        budget="Est. Budget: $80.00",
        proposals="20 to 50",
        location="India",
        skills=["Microsoft Excel", "Formula", "Financial Model"],
        description=("Our cash flow model has broken references and slow array "
                     "formulas. Looking for someone to fix the formulas and document "
                     "how the sheet works."),
    ),
    dict(
        id="021968676050348026879",
        title="Build a web based inventory management system",
        keywords=["web application"],
        posted="3 hours ago",
        type="Fixed price",
        budget="Est. Budget: $450.00",
        proposals="Less than 5",
        location="Netherlands",
        skills=["Web Application", "Laravel", "MySQL", "Admin Panel", "Bootstrap"],
        description=("We need a management system where staff can log stock in and "
                     "out, with user roles, an admin panel and printable reports. "
                     "Clean and simple UI preferred."),
    ),
    dict(
        id="021968676050348026880",
        title="UI/UX design for a SaaS analytics dashboard",
        keywords=["web design UI UX"],
        posted="yesterday",
        type="Hourly: $20.00 - $40.00",
        budget="",
        proposals="10 to 15",
        location="United States",
        skills=["UI/UX Design", "Figma", "Dashboard Design", "Web Design"],
        description=("Redesign the main dashboard screens of our SaaS product. "
                     "Deliverables are Figma wireframes and a high fidelity "
                     "prototype for desktop and tablet."),
    ),
    dict(
        id="021968676050348026881",
        title="React web app frontend for a booking portal",
        keywords=["web application"],
        posted="2 days ago",
        type="Fixed price",
        budget="Est. Budget: $480.00",
        proposals="15 to 20",
        location="Spain",
        skills=["React", "JavaScript", "Frontend", "Responsive", "Tailwind"],
        description=("Build the frontend of a booking web application against an "
                     "existing REST API, including a calendar view and a responsive "
                     "customer portal."),
    ),
    dict(
        id="021968676050348026882",
        title="Unity game developer for mobile puzzle game",
        keywords=["web application"],
        posted="5 hours ago",
        type="Hourly: $25.00 - $50.00",
        budget="",
        proposals="5 to 10",
        location="Poland",
        skills=["Unity 3D", "Game Development", "C#"],
        description=("Looking for a game developer to build levels for our mobile "
                     "puzzle game in Unity. Some web application knowledge useful for "
                     "the leaderboard."),
    ),
    dict(
        id="021968676050348026883",
        title="Cold calling and appointment setting for agency",
        keywords=["web application"],
        posted="yesterday",
        type="Hourly: $8.00 - $15.00",
        budget="",
        proposals="20 to 50",
        location="Philippines",
        skills=["Cold Calling", "Sales", "Telemarketing"],
        description=("We need a sales representative for cold calling small business "
                     "owners and booking demos of our web application. Commission "
                     "only after the trial period."),
    ),
    dict(
        id="021968676050348026884",
        title="Scrape public data and load it into an Excel dashboard",
        keywords=["excel dashboard", "web scraping"],
        posted="8 hours ago",
        type="Fixed price",
        budget="Est. Budget: $220.00",
        proposals="10 to 15",
        location="United States",
        skills=["Web Scraping", "Microsoft Excel", "Python", "Dashboard"],
        description=("Collect pricing data from a handful of public sites weekly and "
                     "load it into an Excel dashboard with pivot tables so our team "
                     "can compare trends."),
    ),
    dict(
        id="021968676050348026885",
        title="Old posting that should be filtered out",
        keywords=["web scraping"],
        posted="2 weeks ago",
        type="Fixed price",
        budget="Est. Budget: $200.00",
        proposals="20 to 50",
        location="United States",
        skills=["Web Scraping"],
        description="This listing is older than the recency window and must not appear.",
    ),
]


def jobs_for_keyword(keyword: str):
    """Sample listings that a given keyword search would return."""
    return [job for job in SAMPLE_JOBS if keyword in job["keywords"]]
