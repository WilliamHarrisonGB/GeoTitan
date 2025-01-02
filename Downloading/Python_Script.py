import aiohttp
import asyncio
import time
import json
import os
import threading
import logging
from typing import Dict, Tuple, List, Optional
import tkinter as tk
from tkinter import ttk, font, messagebox
import ctypes

# --- Configuration ---
BASE_URLS = [
    "",
    # ... add more URLs as needed
]

PARAMS = {
    "where": "1=1",
    "outFields": "*",
    "f": "geojson",
    "resultOffset": 0,
    "resultRecordCount": 1000,
}

MAX_CONCURRENT_REQUESTS_PER_URL = 32  # Max concurrent requests
MAX_RETRIES = 10
RETRY_DELAY = 1  # Initial retry delay in seconds
TIMEOUT = 20  # Timeout for aiohttp requests in seconds
DEBUG_MODE = False # Set to True to enable debug logging
WRITE_BUFFER_SIZE = 50 * 1024 * 1024  # Write to disk after accumulating 50 MB (per URL)

# --- Enable DPI Awareness ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)  # 1 for PROCESS_SYSTEM_DPI_AWARE
except Exception as e:
    logging.warning(f"Failed to set DPI awareness: {e}")

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO if not DEBUG_MODE else logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

# --- UI Class ---
class DownloadProgressUI:
    """Manages the UI for the GeoJSON downloader."""

    def __init__(self, root: tk.Tk, base_urls: List[str]):
        self.root = root
        self.root.title("GeoTitan")
        self.base_urls = base_urls
        self.progress_bars: Dict[
            str, Tuple[ttk.Progressbar, ttk.Progressbar, ttk.Label]
        ] = {}
        self.download_speeds: Dict[str, ttk.Label] = {}
        self.total_downloaded_labels: Dict[str, ttk.Label] = {}
        self.total_downloaded_sizes: Dict[str, float] = {}
        self.queue: asyncio.Queue = asyncio.Queue()
        self.loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self.cancel_event = threading.Event()
        self.write_buffers: Dict[str, bytes] = {}
        self.write_buffer_sizes: Dict[str, int] = {}
        self.create_widgets()

    def create_widgets(self) -> None:
        """Creates the UI elements."""
        self.custom_font = font.Font(family="Helvetica", size=10)

        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)

        for i, base_url in enumerate(self.base_urls):
            url_label = ttk.Label(self.main_frame, text=base_url, font=self.custom_font)
            url_label.grid(row=i * 4, column=0, sticky=tk.W, pady=(5, 0))

            pbar_download = ttk.Progressbar(
                self.main_frame, orient="horizontal", mode="indeterminate", length=300
            )
            pbar_download.grid(
                row=i * 4, column=1, sticky=(tk.W, tk.E), pady=(5, 0), padx=(10, 0)
            )

            speed_label = ttk.Label(
                self.main_frame, text="Speed: N/A", font=self.custom_font
            )
            speed_label.grid(row=i * 4, column=2, sticky=tk.W, pady=(5, 0), padx=(10, 0))
            self.download_speeds[base_url] = speed_label

            pbar_file = ttk.Progressbar(
                self.main_frame, orient="horizontal", mode="determinate", length=300
            )
            pbar_file.grid(
                row=i * 4 + 1, column=1, sticky=(tk.W, tk.E), pady=(0, 5), padx=(10, 0)
            )

            # Label for total downloaded size
            total_downloaded_label = ttk.Label(
                self.main_frame, text="Total Downloaded: 0 MB", font=self.custom_font
            )
            total_downloaded_label.grid(row=i * 4 + 2, column=1, sticky=tk.W, pady=(0, 5))
            self.total_downloaded_labels[base_url] = total_downloaded_label
            self.total_downloaded_sizes[base_url] = 0

            error_label = ttk.Label(
                self.main_frame, text="", font=self.custom_font, foreground="red"
            )
            error_label.grid(row=i * 4 + 3, column=1, sticky=tk.W, pady=(0, 5))

            self.progress_bars[base_url] = (pbar_download, pbar_file, error_label)

        button_frame = ttk.Frame(self.main_frame)
        button_frame.grid(
            row=len(self.base_urls) * 4, column=0, columnspan=3, pady=20
        )
        self.start_button = ttk.Button(
            button_frame, text="Start Download", command=self.start_download
        )
        self.start_button.pack(side="left", padx=5)

        self.cancel_button = ttk.Button(
            button_frame, text="Cancel", command=self.cancel_download, state="disabled"
        )
        self.cancel_button.pack(side="left", padx=5)

        self.main_frame.columnconfigure(1, weight=1)

        self.log_frame = ttk.LabelFrame(self.main_frame, text="Log")
        self.log_frame.grid(
            row=len(self.base_urls) * 4 + 1,
            column=0,
            columnspan=3,
            sticky=(tk.W, tk.E),
            pady=(0, 10),
        )
        self.log_text = tk.Text(self.log_frame, wrap="word", state="disabled", height=10)
        self.log_text.pack(expand=True, fill="both")

    def start_download(self) -> None:
        """Starts the download process in a separate thread."""
        self.start_button.config(state="disabled")
        self.cancel_button.config(state="normal")
        self.cancel_event.clear()
        threading.Thread(target=self.run_async_task, daemon=True).start()

    def cancel_download(self) -> None:
        """Cancels the download process."""
        self.cancel_event.set()
        self.cancel_button.config(state="disabled")
        self.log_message("Cancelling download...")

    def run_async_task(self) -> None:
        """Runs the async tasks in a separate thread."""
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.run_download_tasks())

    async def run_download_tasks(self) -> None:
        """Starts the download tasks."""
        try:
            await main(
                self.queue,
                self.progress_bars,
                self.base_urls,
                self.cancel_event,
            )
            self.root.after(0, self.finish_download)
        except Exception as e:
            self.log_message(f"Error in run_download_tasks: {e}", level="error")
            self.root.after(0, self.finish_download, True)

    def update_progress(self) -> None:
        """Updates the progress bars and labels in the UI."""
        try:
            while not self.queue.empty():
                base_url, update_type, value, speed = self.queue.get_nowait()

                if update_type == "write_buffer":
                    self.handle_write_buffer(base_url, value)
                    continue

                pbar_download, pbar_file, error_label = self.progress_bars[base_url]

                if update_type == "download_size":
                    if pbar_download["mode"] == "indeterminate":
                        pbar_download["mode"] = "determinate"
                    pbar_download["value"] = value
                    self.total_downloaded_sizes[base_url] += value
                    self.total_downloaded_labels[base_url].config(
                        text=f"Total Downloaded: {self.total_downloaded_sizes[base_url] / (1024 * 1024):.2f} MB"
                    )
                elif update_type == "download_speed":
                    self.download_speeds[base_url].config(
                        text=f"Speed: {speed:.2f} MB/s"
                    )
                elif update_type == "file_size":
                    if pbar_file["mode"] == "indeterminate":
                        pbar_file["mode"] = "determinate"
                    pbar_file["value"] = value
                elif update_type == "file_max":
                    pbar_file["maximum"] = value
                elif update_type == "download_max":
                    pbar_download["maximum"] = value
                elif update_type == "error":
                    error_label.config(text=value)
                elif update_type is None:
                    pass
                else:
                    logging.warning(f"Unknown update type: {update_type}")
        except Exception as e:
            self.log_message(f"Error in update_progress: {e}", level="error")
        finally:
            self.root.after(100, self.update_progress)

    def handle_write_buffer(self, base_url: str, chunk: bytes) -> None:
        """Handles buffering and writing data to disk."""
        if base_url not in self.write_buffers:
            self.write_buffers[base_url] = b""
            self.write_buffer_sizes[base_url] = 0

        self.write_buffers[base_url] += chunk
        self.write_buffer_sizes[base_url] += len(chunk)

        if self.write_buffer_sizes[base_url] >= WRITE_BUFFER_SIZE:
            self.flush_buffer(base_url)

    def flush_buffer(self, base_url: str) -> None:
        """Writes the buffered data to disk."""
        if base_url in self.write_buffers:
            try:
                output_filename = f"{base_url.replace('http://', '').replace('https://', '').replace('/', '_')}.geojson"
                with open(output_filename, "ab") as f:  # Open in append binary mode
                    f.write(self.write_buffers[base_url])
                self.write_buffers[base_url] = b""
                self.write_buffer_sizes[base_url] = 0
            except OSError as e:
                error_msg = f"Error writing to file {output_filename}: {e}"
                self.queue.put_nowait((base_url, "error", error_msg, 0))

    def finish_download(self, error=False) -> None:
        """Handles the completion of the download process."""
        for base_url in self.base_urls:
            self.flush_buffer(base_url)  # Flush any remaining data in buffers
        if not error:
            self.log_message("Download process completed.")
        self.start_button.config(state="normal")
        self.cancel_button.config(state="disabled")

    def log_message(self, message: str, level: str = "info") -> None:
        """Logs a message to the log area and console."""
        if level == "error":
            logging.error(message)
        else:
            logging.info(message)
        self.log_text.config(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.config(state="disabled")
        self.log_text.see("end")

# --- Helper Functions ---
def debug_log(message: str) -> None:
    """Logs a debug message if DEBUG_MODE is True."""
    if DEBUG_MODE:
        logging.debug(message)

async def download_chunk(
    base_url: str,
    offset: int,
    queue: asyncio.Queue,
    session: aiohttp.ClientSession,
    progress_bars: Dict[str, Tuple[ttk.Progressbar, ttk.Progressbar]],
    total_size_bytes: int,
    cancel_event: threading.Event,
    max_retries: int = MAX_RETRIES,
    retry_delay: float = RETRY_DELAY,
) -> int:
    """Downloads a chunk of GeoJSON data with retries."""
    local_params = PARAMS.copy()
    local_params["resultOffset"] = offset

    retries = 0
    while retries < max_retries:
        if cancel_event.is_set():
            return 0
        start_time = time.time()
        try:
            async with session.get(
                base_url, params=local_params, timeout=TIMEOUT
            ) as response:
                response.raise_for_status()
                content = await response.json()

                if "features" in content and isinstance(content["features"], list):
                    chunk_size = sum(len(json.dumps(feature).encode("utf-8")) for feature in content["features"])
                else:
                    chunk_size = 0

                elapsed_time = time.time() - start_time
                download_speed = chunk_size / (1024 * 1024) / elapsed_time

                # Update UI
                await queue.put(
                    (
                        base_url,
                        "download_size",
                        chunk_size,
                        download_speed,
                    )
                )
                await queue.put((base_url, "download_speed", 0, download_speed))
                await queue.put((base_url, offset, content, 0))
                return chunk_size
        except (
            aiohttp.ClientResponseError,
            asyncio.TimeoutError,
            aiohttp.ClientError,
        ) as e:
            retries += 1
            error_msg = f"Error downloading chunk at offset {offset} from {base_url}: {e}. Retrying in {retry_delay} seconds..."
            logging.warning(error_msg)
            await queue.put((base_url, "error", error_msg, 0))

            if retries < max_retries:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}"
            logging.error(error_msg)
            await queue.put((base_url, "error", error_msg, 0))
            return 0

    error_msg = f"Failed to download chunk at offset {offset} from {base_url} after {max_retries} retries."
    logging.error(error_msg)
    await queue.put((base_url, "error", error_msg, 0))
    return 0

async def write_to_file(
    queue: asyncio.Queue,
    base_url: str,
    pbar_file: ttk.Progressbar,
    cancel_event: threading.Event,
) -> None:
    """Writes GeoJSON chunks from the queue to a file buffer."""
    written_offsets = set()
    first_chunk = True

    try:
        while not cancel_event.is_set():
            url, offset, chunk, _ = await queue.get()
            if chunk is None:
                queue.task_done()
                break

            if offset not in written_offsets:
                try:
                    if first_chunk:
                        chunk_bytes = b'{"type":"FeatureCollection","features":['
                        first_chunk = False
                    else:
                        chunk_bytes = b',' if "features" in chunk and isinstance(chunk["features"], list) else b''

                    # Check if "features" exists and is a list before processing
                    if "features" in chunk and isinstance(chunk["features"], list):
                        features = json.dumps(chunk["features"])[1:-1].encode("utf-8")
                        chunk_bytes += features

                    await queue.put((base_url, "write_buffer", chunk_bytes, 0))  # Put data in buffer
                    written_offsets.add(offset)

                except Exception as e:
                    error_msg = f"An unexpected error occurred while buffering data: {e}"
                    await queue.put((base_url, "error", error_msg, 0))
                    return

            queue.task_done()

        # Signal that file writing is complete for this URL
        await queue.put((base_url, "write_buffer", b"]}", 0))  # Indicate end of GeoJSON
        await queue.put((base_url, "file_size", float("inf"), 0))

    except Exception as e:
        error_msg = f"An unexpected error occurred: {e}"
        await queue.put((base_url, "error", error_msg, 0))

async def download_from_url(
    base_url: str,
    queue: asyncio.Queue,
    session: aiohttp.ClientSession,
    max_concurrent_requests: int,
    progress_bars: Dict[str, Tuple[ttk.Progressbar, ttk.Progressbar]],
    cancel_event: threading.Event,
) -> None:
    """Manages the download process for a single URL."""
    offset = 0
    total_size_bytes = 0
    total_features = 0

    try:
        async with session.get(
            base_url,
            params={**PARAMS, "returnCountOnly": "true"},
            timeout=TIMEOUT,
        ) as response:
            response.raise_for_status()
            count_data = await response.json()
            if "count" in count_data:
                total_features = count_data["count"]
    except (aiohttp.ClientError, asyncio.TimeoutError, Exception) as e:
        logging.warning(f"Could not determine total feature count for {base_url}: {e}")

    await queue.put((base_url, "download_max", total_size_bytes, 0))
    await queue.put((base_url, "file_max", total_size_bytes, 0))

    pbar_download, pbar_file, _ = progress_bars[base_url]
    pbar_download.config(mode="indeterminate")
    pbar_file.config(maximum=total_size_bytes, mode="indeterminate")

    writer_task = asyncio.create_task(
        write_to_file(queue, base_url, pbar_file, cancel_event)
    )

    tasks = []
    for _ in range(max_concurrent_requests):
        task = asyncio.create_task(
            download_chunk(
                base_url,
                offset,
                queue,
                session,
                progress_bars,
                total_size_bytes,
                cancel_event,
            )
        )
        tasks.append(task)
        offset += PARAMS["resultRecordCount"]

    while not cancel_event.is_set():
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            try:
                task.result()
            except Exception as e:
                logging.error(f"Error in download_chunk task: {e}")

        tasks = list(pending)
        new_tasks = []
        while len(tasks) + len(new_tasks) < max_concurrent_requests:
            if offset < total_features:
                new_task = asyncio.create_task(
                    download_chunk(
                        base_url,
                        offset,
                        queue,
                        session,
                        progress_bars,
                        total_size_bytes,
                        cancel_event,
                    )
                )
                new_tasks.append(new_task)
                offset += PARAMS["resultRecordCount"]
            else:
                break
        tasks.extend(new_tasks)

        if not tasks:
            break
        await asyncio.sleep(0)

    if cancel_event.is_set():
        await queue.put((base_url, "error", "Download cancelled by user.", 0))

    await queue.put((base_url, None, None, None))
    await queue.join()
    await writer_task

# --- Main Function ---
async def main(
    queue: asyncio.Queue,
    progress_bars: Dict[str, Tuple[ttk.Progressbar, ttk.Progressbar]],
    base_urls: List[str],
    cancel_event: threading.Event,
) -> None:
    """Manages the download and writing process for multiple URLs."""
    async with aiohttp.ClientSession() as session:
        download_tasks = []
        for base_url in base_urls:
            task = asyncio.create_task(
                download_from_url(
                    base_url,
                    queue,
                    session,
                    MAX_CONCURRENT_REQUESTS_PER_URL,
                    progress_bars,
                    cancel_event,
                )
            )
            download_tasks.append(task)
        await asyncio.gather(*download_tasks)

# --- Entry Point ---
if __name__ == "__main__":
    root = tk.Tk()
    ui = DownloadProgressUI(root, BASE_URLS)
    root.after(100, ui.update_progress)
    root.mainloop()
