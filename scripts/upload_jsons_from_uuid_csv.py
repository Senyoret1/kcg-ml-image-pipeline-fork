import csv
import requests
import argparse

def upload_jsons_from_csv(csv_file_path):
    api_url = "http://123.176.98.90:8764"

    with open(csv_file_path, mode='r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            job_uuid = row["job_uuid"]
            # Endpoint URL with job_uuid as a query parameter
            endpoint_url = f"{api_url}/queue-ranking/upload?job_uuid={job_uuid}"
            response = requests.post(endpoint_url)  # Use POST instead of GET

            if response.status_code == 200:
                print(f"Successfully processed job UUID: {job_uuid}")
            else:
                print(f"Failed to process job UUID: {job_uuid}. Response: {response.status_code} - {response.text}")

def main():
    parser = argparse.ArgumentParser(description="Upload JSONs from CSV to MinIO via API")
    parser.add_argument("--csv_filepath", type=str, required=True, help="Path to the CSV file")
    
    args = parser.parse_args()
    csv_file_path = args.csv_filepath
    
    upload_jsons_from_csv(csv_file_path)

if __name__ == "__main__":
    main()