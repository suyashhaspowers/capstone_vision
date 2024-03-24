from flask import Flask
from openai import OpenAI
import base64
import errno
import time
import os
import requests
import cv2
import time

from requests.exceptions import ConnectionError

def make_post_request(url, headers, payload, retries=3):
    for _ in range(retries):
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response
        except ConnectionError as e:
            print(f"Error: {e}")
            continue
    raise ConnectionError("Failed to establish connection after multiple retries.")

app = Flask(__name__)

image_directory = "images"
# Get a list of all files in the "images" directory
image_files = [f for f in os.listdir(image_directory) if os.path.isfile(os.path.join(image_directory, f))]

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer "
}

content = """
                You will be given an image of an inventory shelf with 4 rows and 2 columns.
                Your task will be to classify the contents of the boxes of the shelf. Some Boxes are white and some are brown.
                You will do this by reading the labels on the boxes and placing them in a 2D array to indicate its position.
                Think of the shelf as a grid system with 4 rows and 2 columns.
                Boxes on the left side of a row are in the first column.
                Boxes on the right side of a row are in the second column.
                The shelf is a white in color.
                Sometimes rows and columns can be empty.
                Typically, positions that are empty on the shelf are denoted with a green 'X' on the backdrop.
                This 'X' is made with green tape and may not look perfect.
                If you see a green 'X' on the right side of a box, that means the box is in the first column.
                If you see a green 'X' on the left side of a box, that means the box is in the second column.
                The following box labels exist on the boxes:
                1. Sliced Black Olives
                2. Sliced Green Olives
                3. Sliced Dill Pickles
                4. Hot Sliced Banana Peppers
                5. Sliced Jalapeno Peppers 
                # An example output of your response will be:
                # [['Sliced Black Olives', 'Sliced Green Olives'], ['', ''], ['Sliced Dill Pickles', 'Sliced Jalapeno Peppers'], ['', 'Hot Sliced Banana Peppers']]
                # You only need to return the array.
                This means that Sliced Black Olives exists on the first row of the shelf in the first column and Sliced Green Olives exist in the second column.
                This also means that the second row is completely empty.
                This also means that the third row has Sliced Dill Pickles on the first column and Sliced Jalapeno Peppers in the second column.
                The final row is empty in the first column and has Hot Sliced Banana Peppers in the second column.
                Try your best!
"""

content_2 = """
    You are a vision system that tracks food ingredient inventory boxes on a restaurant's shelf.
"""

def encode_image(image_path):
    while True:
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except IOError as e:
            if e.errno != errno.EACCES:
                # Not a "file in use" error, re-raise
                raise
            # File is being written to, wait a bit and retry
            time.sleep(0.1)

def analyze(encoded_image):
    payload = {
        "model": "gpt-4-vision-preview",
        "messages": [
            {
                "role": "system",
                "content": content + content_2
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What is on the shelf?"},
                    {
                        "type": "image_url",
                        "image_url": f"data:image/jpeg;base64,{encoded_image}",
                    }
                ]
            }
        ],
        "max_tokens": 2000,
    }

    try:
        response = make_post_request('https://api.openai.com/v1/chat/completions', headers, payload)
        print(response.text)
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

    return response.json()

@app.route('/')
def main():
    image_paths = []

    # Iterate over the list of image files and encode each one
    for image_file in image_files:
        if ('.png' or '.jpg' or '.jpeg') in image_file:
            image_path = os.path.join(image_directory, image_file)
            image_paths.append(image_path)

    encoded_image = encode_image(image_paths[0])

    print(image_paths)
    return analyze(encoded_image)

@app.route('/run')
def run():

    # Initialize the webcam
    cap = cv2.VideoCapture(0)

    # Set desired resolution (adjust as needed)
    desired_width = 1920
    desired_height = 1080
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, desired_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, desired_height)

    # Check if the webcam is opened correctly
    if not cap.isOpened():
        raise IOError("Cannot open webcam")

    # Wait for the camera to initialize and adjust light levels
    time.sleep(2)

    # while True:
    ret, frame = cap.read()
    if ret:
        # Save the frame as a lossless PNG image
        print("📸 Taking photo of inventory shelf.")
        path = f"{image_directory}/shelf.png"
        cv2.imwrite(path, frame, [cv2.IMWRITE_PNG_COMPRESSION, 0])
    else:
        print("Failed to capture image")

    # Wait for 2 seconds
    time.sleep(2)

    # Release the camera and close all windows
    cap.release()
    cv2.destroyAllWindows()
    

    image_paths = []

    # Iterate over the list of image files and encode each one
    for image_file in image_files:
        if ('.png' or '.jpg' or '.jpeg') in image_file:
            image_path = os.path.join(image_directory, image_file)
            image_paths.append(image_path)

    encoded_image = encode_image(image_paths[0])

    print(image_paths)
    return analyze(encoded_image)
