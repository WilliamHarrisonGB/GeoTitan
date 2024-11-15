import aiohttp
import asyncio
import time
import json

# Base URL for the specific MapServer layer
base_url = "....query"
params = {
    "where": "1=1",
    "outFields": "*",
    "f": "geojson",
    "resultOffset": 0,
    "resultRecordCount": 1000
}

# Function to download a chunk of data
async def download_chunk(offset, queue, session):
    local_params = params.copy()
    local_params["resultOffset"] = offset
    start_time = time.time()
    try:
        async with session.get(base_url, params=local_params) as response:
            response.raise_for_status()
            content = await response.json()
            elapsed_time = time.time() - start_time
            download_speed = len(json.dumps(content)) / (1024 * 1024) / elapsed_time  # Convert to MB/s
            print(f"Chunk at offset {offset} downloaded at {download_speed:.2f} MB/s")
            await queue.put((offset, content))
    except aiohttp.ClientError as e:
        print(f"Error: {e}")
        await queue.put((offset, None))

# Function to write data to file
async def write_to_file(queue, file):
    written_offsets = set()
    first_chunk = True
    while True:
        offset, chunk = await queue.get()
        if chunk is None:
            break
        if offset not in written_offsets:
            if first_chunk:
                # Write the initial part of the GeoJSON
                file.write(b'{"type":"FeatureCollection","features":[')
                first_chunk = False
            else:
                # Only add a comma if the previous chunk had features
                if "features" in chunk and chunk["features"]:
                    file.write(b',')
            # Write the features from the chunk if they exist
            if "features" in chunk and chunk["features"]:
                features = json.dumps(chunk["features"])[1:-1]  # Remove the surrounding brackets
                if features:
                    file.write(features.encode('utf-8'))
            written_offsets.add(offset)
            print(f"Chunk at offset {offset} written to file.")
        queue.task_done()
    # Close the GeoJSON structure
    file.write(b']}')

# Main function to manage tasks
async def main():
    start_time = time.time()
    queue = asyncio.Queue()
    offset = 0
    num_tasks = 128  # Number of concurrent tasks

    async with aiohttp.ClientSession() as session:
        with open('land_records.geojson', 'wb') as f:
            writer_task = asyncio.create_task(write_to_file(queue, f))

            while True:
                tasks = []
                for _ in range(num_tasks):
                    tasks.append(download_chunk(offset, queue, session))
                    offset += params["resultRecordCount"]

                await asyncio.gather(*tasks)

                # Check if the number of returned features is less than the max count
                async with session.get(base_url, params={**params, "resultOffset": offset}) as response:
                    data = await response.json()
                    if "features" not in data or len(data["features"]) < params["resultRecordCount"]:
                        break

            await queue.put((None, None))
            await writer_task

    elapsed_time = time.time() - start_time
    file_size = offset * params["resultRecordCount"] / (1024 * 1024)  # Convert to MB
    download_speed = file_size / elapsed_time
    print(f"Download complete in {elapsed_time:.2f} seconds at {download_speed:.2f} MB/s.")

if __name__ == "__main__":
    asyncio.run(main())
