# unuseable right now due to unknown update type warnings, will push soon.
# GeoTitan: A Concurrent GeoJSON Downloader

GeoTitan is a Python-based GUI application designed to efficiently download large GeoJSON datasets from ArcGIS REST Feature Servers. It leverages asynchronous programming and concurrency to achieve high download speeds while providing a user-friendly interface for monitoring progress.

## Features

*   **Concurrent Downloads:** Downloads data from multiple URLs simultaneously, significantly reducing overall download time.
*   **Configurable Concurrency:** Allows adjustment of the maximum number of concurrent requests per URL to balance speed and server load.
*   **Buffering:** Buffers downloaded data in memory and writes to disk in large chunks, improving efficiency and reducing disk I/O.
*   **Retry Mechanism:** Automatically retries failed downloads with exponential backoff, enhancing robustness against network issues.
*   **Progress Monitoring:** Displays real-time progress bars for each URL, showing download speed, total downloaded data, and file writing progress.
*   **Error Handling:** Gracefully handles various error conditions, including network errors, server errors, and data parsing errors. Reports errors in the UI and logs them for debugging.
*   **Cancellation:** Allows users to cancel the download process at any time.
*   **Logging:** Provides detailed logging of events, warnings, and errors for monitoring and troubleshooting.
*   **User-Friendly GUI:** Built with Tkinter, providing a simple and intuitive interface for interacting with the application.

## Requirements

*   Python 3.10 or higher
*   `aiohttp` library
*   `tkinter` library
*   `tqdm` library

## Installation

1. **Just install it as zip**


## Usage

1. **Configure `BASE_URLS`:**
    *   Open the `python_script.py` file.
    *   Modify the `BASE_URLS` list to include the URLs of the ArcGIS REST Feature Server layers you want to download.
    *   Example:

        ```python
        BASE_URLS = [
            "https://gis.fdot.gov/arcgis/rest/services/EXAMPLE/EXAMPLE/11/query",
            "https://services.arcgis.com/EXAMPLE/ArcGIS/rest/services/USA_States/FeatureServer/0/query",
        ]
        ```

2. **Adjust Parameters (Optional):**
    *   Modify the configuration parameters at the top of the `python_script.py` file to fine-tune the download process:
        *   `MAX_CONCURRENT_REQUESTS_PER_URL`: Maximum concurrent requests per URL.
        *   `DELAY_BETWEEN_REQUESTS_PER_URL`: Delay between requests.
        *   `MAX_RETRIES`: Maximum retry attempts for failed chunks.
        *   `RETRY_DELAY`: Initial retry delay.
        *   `TIMEOUT`: Timeout for HTTP requests.
        *   `WRITE_BUFFER_SIZE`: Buffer size before writing to disk.

3. **Run the application:**

    ```bash
    python python_script.py
    ```

4. **Start Download:**
    *   Click the "Start Download" button in the UI.

5. **Monitor Progress:**
    *   Observe the progress bars, download speeds, and total downloaded data for each URL.
    *   Check the "Log" area for any errors or warnings.

6. **Cancel Download (Optional):**
    *   Click the "Cancel" button to stop the download process.

## Limitations

*   **Server-Side Limits:** The download speed and success are ultimately limited by the capabilities and rate limits of the ArcGIS REST server, which may rate limit you.
*   **GeoJSON Format:** This application is specifically designed for downloading GeoJSON data. It may not work correctly with other data formats.
*   **Error Handling:** While the code includes error handling, unexpected server responses or edge cases in the data format might still cause issues.
*   **Memory Usage:** Buffering large amounts of data can consume significant memory. The `WRITE_BUFFER_SIZE` parameter should be adjusted based on available system resources.
*   **No Authentication:** The current version does not support authentication. It is only suitable for downloading publicly accessible GeoJSON data.

## Troubleshooting

*   **"Unknown update type" warnings:** This usually indicates that the server is returning data in an unexpected format or that there's an error in the parsing logic. Check the debug logs for more details and ensure that the server response conforms to the expected GeoJSON structure.
*   **"TypeError: 'int' object is not iterable" error:** This error can occur if a chunk of data doesn't have the expected "features" key or if the value associated with "features" is not a list. Review the error handling and data validation in the `write_to_file` function.
*   **Slow Download Speeds:** If download speeds are consistently slow, try reducing `MAX_CONCURRENT_REQUESTS_PER_URL` or increasing `TIMEOUT`. Also, check your network connection and the server's capacity.
*   **UI Freezing:** If the UI becomes unresponsive, it might be due to blocking operations in the main thread. Ensure that all long-running operations (like network requests and file writing) are performed in separate threads or asynchronous tasks.

## Contributing

Contributions to GeoTitan are welcome! If you find a bug or want to suggest an improvement, please open an issue or submit a pull request on the GitHub repository.
