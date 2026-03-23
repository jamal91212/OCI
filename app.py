from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import time
import traceback

app = Flask(__name__)
CORS(app)

# SEC EDGAR requires a user agent
HEADERS = {
    'User-Agent': 'Ashton analyst@example.com' # Replace with actual email
}

# SEC EDGAR rate limiting states max 10 requests per second.
def sec_request(url):
    time.sleep(0.1) # Ensure we don't hit 10/s
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()

@app.route('/api/sec/filings', methods=['GET'])
def get_filings():
    ticker = request.args.get('ticker')
    if not ticker:
        return jsonify({"error": "Ticker is required"}), 400
    
    ticker = ticker.upper()
    try:
        # Get CIK for the ticker
        tickers_url = "https://www.sec.gov/files/company_tickers.json"
        res = requests.get(tickers_url, headers=HEADERS)
        res.raise_for_status()
        ticker_data = res.json()
        
        cik = None
        for key, value in ticker_data.items():
            if value['ticker'] == ticker:
                cik = str(value['cik_str']).zfill(10)
                break
                
        if not cik:
            return jsonify({"error": f"Invalid ticker: {ticker}"}), 404
            
        # Get filings for the CIK
        submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        sub_res = sec_request(submissions_url)
        
        filings = sub_res.get('filings', {}).get('recent', {})
        if not filings:
            return jsonify({"error": "No recent filings found."}), 404
            
        forms = filings.get('form', [])
        dates = filings.get('filingDate', [])
        accessions = filings.get('accessionNumber', [])
        primary_docs = filings.get('primaryDocument', [])
        
        results = []
        for i, form in enumerate(forms):
            if form in ['10-K', '10-Q', '8-K']:
                acc_no_dash = accessions[i].replace('-', '')
                doc_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_no_dash}/{primary_docs[i]}"
                results.append({
                    "form": form,
                    "date": dates[i],
                    "url": doc_url
                })
                if len(results) >= 15: # Limit to 15 recent filings
                    break
                    
        return jsonify({"filings": results})
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Failed to fetch SEC filings.", "details": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
