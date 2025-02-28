import os
import json
import csv
import geojson
import time
import random
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

class EarthquakeScraper:
    def __init__(self):
        self.base_url = "https://www.seismonepal.gov.np/earthquakes/index?page="
        self.page_num = 1
        self.data_list = []
        self.existing_data = set()
        self.load_existing_data()

    def load_existing_data(self):
        try:
            with open("earthquakes.json", "r", encoding="utf-8") as f:
                existing_records = json.load(f)
                self.existing_data = {record["id"] for record in existing_records}
        except (FileNotFoundError, json.JSONDecodeError):
            self.existing_data = set()

    def run(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context()
            page = context.new_page()

            while True:
                url = f"{self.base_url}{self.page_num}"
                print(f"Scraping page {self.page_num}: {url}")
                page.goto(url)
                try:
                    page.wait_for_selector("table.table-striped", timeout=10000)
                except:
                    print("No table found or page timed out. Stopping.")
                    break

                html = page.content()
                new_data = self.parse_page(html)

                if new_data:
                    self.export_data(new_data)
                    print(f"Found {len(new_data)} new records on page {self.page_num}.")
                else:
                    # If a page has zero new data, we assume older pages won't have anything new
                    print(f"No new data found on page {self.page_num}. Stopping here.")
                    break

                # If there's a next page, keep going; otherwise break
                if not self.check_next_page(html):
                    print("No further pages found. Done scraping.")
                    break

                self.page_num += 1
                time.sleep(random.uniform(1, 5))

            browser.close()

    def parse_page(self, html):
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("table.table-striped tbody tr")
        new_data = []

        for row in rows:
            record = self.extract_record(row)
            if record and record["id"] not in self.existing_data:
                self.existing_data.add(record["id"])
                self.data_list.append(record)
                new_data.append(record)

        return new_data

    def extract_record(self, row):
        try:
            cols = row.find_all("td")
            record_id = cols[0].get_text(strip=True)

            date_text = cols[1].get_text("\n", strip=True).split("\n")
            date_bs = date_text[0].replace("B.S.:", "").strip() if len(date_text) > 0 else ""
            date_ad = date_text[1].replace("A.D.:", "").strip() if len(date_text) > 1 else ""

            time_text = cols[2].get_text("\n", strip=True).split("\n")
            local_time = time_text[0].replace("Local:", "").strip() if len(time_text) > 0 else ""
            utc_time = time_text[1].replace("UTC:", "").strip() if len(time_text) > 1 else ""

            latitude = float(cols[3].get_text(strip=True))
            longitude = float(cols[4].get_text(strip=True))
            magnitude = float(cols[5].get_text(strip=True))

            epicenter_el = cols[6].find("a")
            epicenter = epicenter_el.get_text(strip=True) if epicenter_el else ""

            return {
                "id": record_id,
                "date_bs": date_bs,
                "date_ad": date_ad,
                "local_time": local_time,
                "utc_time": utc_time,
                "latitude": latitude,
                "longitude": longitude,
                "magnitude": magnitude,
                "epicenter": epicenter
            }
        except (IndexError, ValueError, AttributeError):
            return None

    def check_next_page(self, html):
        """Returns True if there's a next page link; otherwise False."""
        soup = BeautifulSoup(html, "html.parser")
        active_li = soup.select_one("ul.pagination li.active")
        if not active_li:
            return False
        next_li = active_li.find_next_sibling("li")
        return bool(next_li and next_li.find("a"))

    def export_data(self, new_data):
        self.export_csv(new_data)
        self.export_json(new_data)
        self.export_geojson(new_data)

    def export_csv(self, new_data):
        file_exists = os.path.isfile("earthquakes.csv")
        with open("earthquakes.csv", "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=new_data[0].keys())
            if not file_exists:
                writer.writeheader()
            writer.writerows(new_data)

    def export_json(self, new_data):
        try:
            with open("earthquakes.json", "r", encoding="utf-8") as f:
                existing_records = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            existing_records = []
        existing_records.extend(new_data)
        with open("earthquakes.json", "w", encoding="utf-8") as f:
            json.dump(existing_records, f, indent=4)

    def export_geojson(self, new_data):
        try:
            with open("earthquakes.geojson", "r", encoding="utf-8") as f:
                existing_geojson = geojson.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            existing_geojson = {"type": "FeatureCollection", "features": []}

        features = []
        for item in new_data:
            point = geojson.Point((item["longitude"], item["latitude"]))
            props = {k: v for k, v in item.items() if k not in ["longitude", "latitude"]}
            features.append(geojson.Feature(geometry=point, properties=props))

        existing_geojson["features"].extend(features)
        with open("earthquakes.geojson", "w", encoding="utf-8") as f:
            geojson.dump(existing_geojson, f, indent=4)


if __name__ == "__main__":
    scraper = EarthquakeScraper()
    scraper.run()
