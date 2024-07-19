import cv2
import pytesseract
import pandas as pd
import re
import streamlit as st
import os
import platform
import subprocess
from datetime import datetime, timedelta
import numpy as np

# Ensure the Tesseract path is correctly set
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
else:
    pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

def convert_to_h264(input_video_path, output_video_path):
    command = [
        'ffmpeg', '-y',
        '-i', input_video_path,
        '-c:v', 'libx264',
        output_video_path
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def extract_timestamps_from_video(video_path, fps, nth_seconds):
    data = []
    cap = cv2.VideoCapture(video_path)
    frame_num = 0

    while cap.isOpened():
        frame_exists, frame = cap.read()
        frame_num += 1
        
        if frame_exists and frame_num % (fps * nth_seconds) == 0:
            secs = round(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000)
            print("Frame {} @{}s".format(frame_num, secs))
            
            x, y, w, h = 0, 0, 850, 50
            timestamp_crop = frame[y:y+h, x:x+w]
            cv2.imshow('timestamp', timestamp_crop)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            timestamp_grey = cv2.cvtColor(timestamp_crop, cv2.COLOR_BGR2GRAY)
            _, timestamp_thresh = cv2.threshold(timestamp_grey, 127, 255, cv2.THRESH_BINARY)
            cv2.imshow("thresholded timestamp", timestamp_thresh)
            
            candidate_str = pytesseract.image_to_string(timestamp_grey, config='--psm 7')
            regex_str = r'Date:\s(\d{4}-\d{2}-\d{2})\sTime:\s(\d{2}:\d{2}:\d{2}\s(?:AM|PM))\sFrame:\s(\d{2}:\d{2}:\d{2}:\d{2})'
            
            match = re.match(regex_str, candidate_str)
            if match:
                date_str, time_str, frame_str = match.groups()
                print("** Date: {} Time: {} Frame: {} @ {}s".format(date_str, time_str, frame_str, secs))
                data.append([date_str, time_str, frame_str, secs])
    
    cap.release()
    cv2.destroyAllWindows()
    return data

def main():
    st.set_page_config(page_title="Video Player", page_icon="📹", layout="centered")

    uploaded_file = st.file_uploader("Upload a video file (MP4, AVI, MOV)", type=["mp4", "avi", "mov"])

    if uploaded_file:
        os.makedirs("./assets", exist_ok=True)
        video_path = "./assets/out.mp4"
        h264_video_path = "./assets/out_h264.mp4"

        with open(video_path, 'wb') as vid:
            vid.write(uploaded_file.read())

        convert_to_h264(video_path, h264_video_path)

        uploaded_csv = st.file_uploader("Upload a CSV file", type=["csv"])

        if 'jump_time_input' not in st.session_state:
            st.session_state.jump_time_input = "00:00:00"
        if 'previous_display' not in st.session_state:
            st.session_state.previous_display = None

        if uploaded_csv:
            df = pd.read_csv(uploaded_csv)
            fps = int(cv2.VideoCapture(h264_video_path).get(cv2.CAP_PROP_FPS))
            nth_seconds = 1  # Change this value based on how frequently you want to capture frames
            
            extracted_timestamps = extract_timestamps_from_video(h264_video_path, fps, nth_seconds)
            st.write("Extracted Timestamps:", extracted_timestamps)
            
            if extracted_timestamps:
                initial_time = extracted_timestamps[0][1]  # Initial time from the first timestamp
                end_time = extracted_timestamps[-1][1]    # End time from the last timestamp

                if initial_time is not None:
                    initial_time_dt = datetime.strptime(initial_time, '%I:%M:%S %p')
                else:
                    initial_time_dt = None
                
                if end_time is not None:
                    end_time_str = end_time
                else:
                    end_time_str = None

                if not df.empty and initial_time_dt and end_time_str:
                    col1, col2 = st.columns(2)
                    with col1:
                        column = st.selectbox('Select a column', df.columns.tolist(), index=0)

                    with col2:
                        display_options = ["Select"] + df[column].astype(str).tolist()
                        display = st.selectbox("Select a value", display_options, index=0)

                    if column and display != "Select":
                        if st.session_state.previous_display != display:
                            st.session_state.jump_time_input = "00:00:00"
                            st.session_state.previous_display = display
                            st.experimental_rerun()

                        filtered_df = df[df[column].astype(str) == display]
                        st.write("Filtered Data:", filtered_df)

                        if not filtered_df.empty:
                            date_time_str = filtered_df["DATE AND TIME"].iloc[0]

                            # Extract time and convert to seconds
                            time_parts = date_time_str.split()
                            if len(time_parts) > 0:
                                time_str = time_parts[-1]

                                try:
                                    extracted_time_dt = datetime.strptime(time_str, '%I:%M:%S %p')

                                    # Ensure the extracted time is within the valid range
                                    if initial_time_dt <= extracted_time_dt <= datetime.strptime(end_time_str, '%I:%M:%S %p'):
                                        extracted_time_seconds = (extracted_time_dt - initial_time_dt).total_seconds()
                                        jump_seconds = 0
                                        if initial_time and end_time:
                                            c1, c2 = st.columns(2)
                                            with c1:
                                                st.write("Initial Time from Video:", initial_time)
                                            with c2:
                                                st.write("End Time from Video:", end_time)

                                            col1, col2 = st.columns(2)
                                            with col1:
                                                st.write("**Start Time**")
                                                start_time_input = st.text_input("", initial_time, key="start_time")
                                            with col2:
                                                st.write("**Jump Time**")
                                                st.session_state.jump_time_input = st.text_input(
                                                    "",
                                                    st.session_state.jump_time_input,
                                                    key="jump_time"
                                                )

                                            jump_time_dt = datetime.strptime(
                                                st.session_state.jump_time_input, '%I:%M:%S %p'
                                            ) if st.session_state.jump_time_input else 0

                                            if jump_time_dt and jump_time_dt >= extracted_time_dt:
                                                jump_seconds = (jump_time_dt - extracted_time_dt).total_seconds()

                                        # Play video from extracted time if video exists
                                        if os.path.exists(h264_video_path):
                                            st.video(h264_video_path, start_time=extracted_time_seconds + jump_seconds,
                                                     format='video/mp4', autoplay=True)
                                        else:
                                            st.write("Error: Video file not found at:", h264_video_path)
                                    else:
                                        st.write("Extracted time is out of the valid range. Playing from the start.")
                                except Exception as e:
                                    st.write("Error parsing time:", e, "Playing from the start.")
                            else:
                                st.write("Time string is empty. Playing from the start.")
                        else:
                            st.write("No matching value found in the selected column. Playing from the start.")
                else:
                    st.write("CSV file is empty or video time information is missing.")
    else:
        st.write("Upload a video file to start.")

if __name__ == "__main__":
    main()
