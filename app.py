import cv2
import pytesseract
import pandas as pd
import re
import streamlit as st
import os
import platform
import subprocess
from datetime import datetime, timedelta

# Ensure the Tesseract path is correctly set
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r".\computer-visions\Tesseract-OCR\tesseract.exe"
else:
    pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

def extract_timestamp(frame, x=0, y=0, w=850, h=50):
    try:
        timestamp_crop = frame[y:y+h, x:x+w]
        timestamp_grey = cv2.cvtColor(timestamp_crop, cv2.COLOR_BGR2GRAY)
        _, timestamp_thresh = cv2.threshold(timestamp_grey, 127, 255, cv2.THRESH_BINARY)
        candidate_str = pytesseract.image_to_string(timestamp_thresh, config='--psm 6')
        print("Extracted Text:", candidate_str)
        
        regex_str = r'Date:\s(\d{4}-\d{2}-\d{2})\sTime:\s(\d{2}:\d{2}:\d{2}\s(?:AM|PM))\sFrame:\s(\d{2}:\d{2}:\d{2}:\d{2})'
        match = re.search(regex_str, candidate_str)
        
        if match:
            date_str, time_str, frame_str = match.groups()
            return date_str, time_str, frame_str
    except Exception as e:
        print(f"Error extracting timestamp: {e}")
    return None

def get_video_timestamp(video_path, frame_position):
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_position)
    ret, frame = cap.read()
    cap.release()
    if ret:
        return extract_timestamp(frame)
    return None

def get_initial_time(video_path):
    timestamp = get_video_timestamp(video_path, 0)
    return timestamp[1] if timestamp else "00:00:00 AM"

def get_video_end_time(video_path):
    cap = cv2.VideoCapture(video_path)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    timestamp = get_video_timestamp(video_path, frame_count - 1)
    cap.release()
    return timestamp[1] if timestamp else "00:00:00 AM"

def convert_to_h264(input_video_path, output_video_path):
    ffmpeg_path = r".\computer-visions\ffmpeg-7.0.1\bin\ffmpeg.exe"
    command = [
        ffmpeg_path, '-y',
        '-i', input_video_path,
        '-c:v', 'libx264',
        output_video_path
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

@st.cache_data
def process_video(uploaded_file):
    os.makedirs("./assets", exist_ok=True)
    video_path = "./assets/out.mp4"
    h264_video_path = "./assets/out_h264.mp4"

    with open(video_path, 'wb') as vid:
        vid.write(uploaded_file.read())

    convert_to_h264(video_path, h264_video_path)
    return h264_video_path

def parse_12_hour_time(time_str):
    try:
        return datetime.strptime(time_str, '%I:%M:%S %p')
    except ValueError:
        return None

def parse_24_hour_time(time_str):
    try:
        return datetime.strptime(time_str, '%H:%M:%S')
    except ValueError:
        return None

def parse_time(time_str):
    dt = parse_12_hour_time(time_str)
    if dt:
        return dt
    
    dt = parse_24_hour_time(time_str)
    if dt:
        return dt
    
    return None

def time_to_seconds(time_str):
    dt = parse_time(time_str)
    if dt:
        return dt.hour * 3600 + dt.minute * 60 + dt.second
    return 0

def seconds_to_time(seconds):
    return str(timedelta(seconds=seconds))

def main():
    st.set_page_config(page_title="Video Player", page_icon="📹", layout="centered")

    uploaded_file = st.file_uploader("Upload a video file (MP4, AVI, MOV)", type=["mp4", "avi", "mov"])

    if uploaded_file:
        h264_video_path = process_video(uploaded_file)

        uploaded_csv = st.file_uploader("Upload a CSV file", type=["csv"])

        if 'jump_time_input' not in st.session_state:
            st.session_state.jump_time_input = "00:00:00"
        if 'previous_display' not in st.session_state:
            st.session_state.previous_display = None

        if uploaded_csv:
            df = pd.read_csv(uploaded_csv)
            initial_time_str = get_initial_time(h264_video_path)
            end_time_str = get_video_end_time(h264_video_path)
            initial_time_dt = parse_time(initial_time_str)
            end_time_dt = parse_time(end_time_str)

            if not df.empty:
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
                        time_parts = date_time_str.split()
                        if len(time_parts) > 0:
                            time_str = time_parts[-1]

                            extracted_time_dt = parse_time(time_str)
                            if not extracted_time_dt:
                                st.write("Error parsing extracted time. Playing from the start.")
                                extracted_time_dt = initial_time_dt

                            if initial_time_dt and end_time_dt and initial_time_dt <= extracted_time_dt <= end_time_dt:
                                extracted_time_seconds = (extracted_time_dt - initial_time_dt).total_seconds()
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write("Initial Time from Video:", list(str(initial_time_dt).split(" "))[1])
                                with col2:
                                    st.write("End Time from Video:", list(str(end_time_dt).split(" "))[1])
                                c1, c2 = st.columns(2)
                                with c1:
                                    st.write("**Start Time**")
                                    start_time_input = st.text_input("", initial_time_str, key="start_time")
                                with c2:
                                    st.write("**Jump Time**")
                                    jump_time_input = st.text_input("", st.session_state.jump_time_input, key="jump_time")

                                if not jump_time_input:
                                    st.write("Jump Time input is empty. Defaulting to 00:00:00.")
                                    jump_time_input = "00:00:00"

                                try:
                                    jump_time_dt = parse_time(jump_time_input)
                                    if jump_time_dt:
                                        jump_seconds = time_to_seconds(jump_time_input)
                                    else:
                                        st.write("Invalid jump time format. Defaulting to 00:00:00.")
                                        jump_seconds = 0
                                except ValueError:
                                    st.write("Error in jump time input. Defaulting to 00:00:00.")
                                    jump_seconds = 0

                                start_time_in_seconds = extracted_time_seconds - jump_seconds
                                total_video_duration_seconds = (end_time_dt - initial_time_dt).total_seconds()

                                initial_time_seconds = time_to_seconds(list(str(initial_time_dt).split(" "))[1])
                                if jump_seconds:
                                    jump_seconds = jump_seconds - initial_time_seconds
                                
                                if jump_seconds:
                                    start_time_in_seconds = jump_seconds
                                elif start_time_in_seconds < 0:
                                    start_time_in_seconds = 0
                                elif start_time_in_seconds > total_video_duration_seconds:
                                    start_time_in_seconds = total_video_duration_seconds

                                if os.path.exists(h264_video_path):
                                    st.video(h264_video_path, start_time=start_time_in_seconds, format='video/mp4', autoplay=True)
                                else:
                                    st.write("Error: Video file not found at:", h264_video_path)
                            else:
                                st.write("Extracted time is out of the valid range. Playing from the start.")
                        else:
                            st.write("Time string is empty. Playing from the start.")
                    else:
                        st.write("No matching value found in the selected column. Playing from the start.")
            else:
                st.write("CSV file is empty.")
    else:
        st.write("Upload a video file to start.")

if __name__ == "__main__":
    main()
