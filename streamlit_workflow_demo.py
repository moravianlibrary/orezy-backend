import os
import cv2
import numpy as np
import streamlit as st
import requests
import time

from app.core.utils import denormalize_bbox
from app.db.schemas import TaskState


def show_results(results):
    for filepath, scan_data in results:
        im = cv2.imread(filepath)
        im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
        h, w = im.shape[0], im.shape[1]

        for page in scan_data["pages"]:
            (xc, yc, ww, hh) = denormalize_bbox(
                (page["xc"], page["yc"], page["width"], page["height"]),
                w,
                h,
            )
            rrect = ((xc, yc), (ww, hh), -page["angle"])
            pts = cv2.boxPoints(rrect)  # float32, order is consistent (clockwise)
            pts = np.intp(np.round(pts))  # convert to int for drawing
            cv2.polylines(im, [pts], isClosed=True, color=(0, 255, 0), thickness=4)
            # Draw dot at center
            cv2.circle(
                im, (int(xc), int(yc)), radius=10, color=(255, 0, 0), thickness=10
            )

        st.image(im, width=600)
        st.write("Page flags:", [page["flags"] for page in scan_data["pages"]])


def main():
    headers = {"Authorization": f"Bearer {os.getenv('WEBAPP_TOKEN')}"}
    st.title("Autocrop workflow demo")

    filepath = st.text_input(
        "Scan filepath",
        "",
    )

    if st.button("Generate crop boxes"):
        with st.spinner("Generating crop boxes..."):
            files = sorted(os.listdir(filepath))
            filepaths = [
                os.path.join(filepath, f)
                for f in files
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".tiff", ".bmp"))
            ]
            st.write(len(filepaths))
            # Make POST request to create the workflow
            response = requests.post(
                "http://localhost:8000/ndk/create",
                json={
                    "filelist": filepaths,
                },
                headers=headers,
            )
            result = response.json()
            st.write(result)
            st.success(f"Queued {len(files)} images.")

            # Query if completed
            while result["state"] != TaskState.ready:
                st.info(f"Current state: {result['state']}")
                time.sleep(10)
                response = requests.get(
                    f"http://localhost:8000/ndk/{result['id']}/status",
                    headers=headers,
                )
                result = response.json()

                if result["state"] == TaskState.failed:
                    st.error("Workflow failed.")
                    return

            # Get all tramsformation instructions
            st.success("All images processed successfully.")
            response = requests.get(
                f"http://localhost:8000/{result['id']}/all-scans",
                headers=headers,
            )
            results = response.json()

            show_results(zip(filepaths, results))


main()
