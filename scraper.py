import requests
from bs4 import BeautifulSoup
import json

# URL to scrape
url = "https://www.emmi-benchmarks.eu/benchmarks/euribor/rate/"

# Add your cookies here - you can copy them from the browser's developer tools
headers = {
    "Cookie": "ARRAffinitySameSite=f3fa9d65bbfa688d29a1a91ccdec91ae26ed93dc3155948db01783a752e0543f;TiPMix=23.12935049293654;CookieConsent={stamp:%27dB4fkIW4iYMVG8ecCTSj3WgtEyUgf/5dnNq2ZFZs3LT7/ANiXRDG7w==%27%2Cnecessary:true%2Cpreferences:true%2Cstatistics:true%2Cmarketing:true%2Cmethod:%27explicit%27%2Cver:1%2Cutc:1771582220163%2Cregion:%27nl%27};x-ms-routing-name=self;__RequestVerificationToken=YmMVyz7TUNWtWB7qzG0r2bTPACdRB3_Jp6wgYOzwohlmA2WbzRoo7mHB5nI8vJhWxJueocppJRGdlW3biET5DgbMkrulf36cV3ldLKsSa3E1;ai_session=PBilZ|1771586213547.7|1771586213547.7;ai_user=9ys3Y|2026-02-20T10:10:21.150Z;ARRAffinity=f3fa9d65bbfa688d29a1a91ccdec91ae26ed93dc3155948db01783a752e0543f;ASP.NET_SessionId=55jyrkrbl0e22sblkposnhga"
}
response = requests.get(url, headers=headers)

# Parse HTML
soup = BeautifulSoup(response.content, 'html.parser')

# Find all table rows
data = []

# Find the tbody element and iterate through rows
tbody = soup.find('tbody')
if tbody:
    rows = tbody.find_all('tr')
    
    for row in rows:
        # Get the date from th element
        th = row.find('th', scope='row')
        if th:
            date = th.get_text(strip=True)
            
            # Get all td elements
            tds = row.find_all('td')
            
            # Get the second td (index 1) if it exists
            if len(tds) >= 2:
                second_value = tds[1].get_text(strip=True)
                
                data.append({
                    "date": date,
                    "value": second_value
                })

# Convert to JSON and print
json_output = json.dumps(data, indent=2)
print(json_output)
