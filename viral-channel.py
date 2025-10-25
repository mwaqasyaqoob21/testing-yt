import streamlit as st
import requests
from datetime import datetime, timedelta

# YouTube API Key
API_KEY = "AIzaSyDJcigV37FRMhkO73M97OUm85tb82y6HM0"  # Enter your API Key here
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels"

# Country list for dropdown (example, can be expanded as needed)
countries = ['India', 'United States', 'United Kingdom', 'Australia', 'Canada', 'Germany', 'Japan', 'Brazil']

# Streamlit App Title
st.title("Discover Newly Launched YouTube Channels")

# Dropdown for Country Selection
selected_country = st.selectbox("Select a Country", countries)

# Dropdown for selecting the time period (7 days, 14 days, 28 days)
time_period = st.selectbox("Select Time Period", ["7 Days", "14 Days", "28 Days"])

# Filter to only show channels with 1k-5k subscribers
min_subs = 1000
max_subs = 5000

# Fetch Data Button
if st.button("Fetch Data"):
    try:
        # Set date range based on selected time period
        if time_period == "7 Days":
            start_date = (datetime.utcnow() - timedelta(days=7)).isoformat("T") + "Z"
        elif time_period == "14 Days":
            start_date = (datetime.utcnow() - timedelta(days=14)).isoformat("T") + "Z"
        else:
            start_date = (datetime.utcnow() - timedelta(days=28)).isoformat("T") + "Z"

        all_results = []

        # Fetch channels based on the selected country and time period
        search_params = {
            "part": "snippet",
            "q": selected_country,
            "type": "channel",
            "publishedAfter": start_date,
            "maxResults": 5,
            "key": API_KEY,
        }

        response = requests.get(YOUTUBE_SEARCH_URL, params=search_params)
        data = response.json()

        if "items" not in data or not data["items"]:
            st.warning(f"No newly launched channels found for {selected_country} in the last {time_period}.")
        else:
            # Process each channel
            for channel in data["items"]:
                channel_id = channel["snippet"]["channelId"]
                channel_name = channel["snippet"]["channelTitle"]
                channel_url = f"https://www.youtube.com/channel/{channel_id}"

                # Fetch channel stats to get the subscriber count
                channel_params = {"part": "statistics", "id": channel_id, "key": API_KEY}
                channel_response = requests.get(YOUTUBE_CHANNEL_URL, params=channel_params)
                channel_data = channel_response.json()

                if "items" in channel_data and channel_data["items"]:
                    subs = int(channel_data["items"][0]["statistics"]["subscriberCount"])

                    # Filter for channels with 1k-5k subscribers
                    if min_subs <= subs <= max_subs:
                        # Fetch top 5 videos from this channel
                        video_params = {
                            "part": "snippet,statistics",
                            "channelId": channel_id,
                            "order": "viewCount",  # Sorting by view count
                            "maxResults": 5,
                            "key": API_KEY,
                        }

                        video_response = requests.get(YOUTUBE_SEARCH_URL, params=video_params)
                        video_data = video_response.json()

                        if "items" in video_data and video_data["items"]:
                            video_details = []

                            for video in video_data["items"]:
                                video_id = video["id"]["videoId"]
                                title = video["snippet"]["title"]
                                video_url = f"https://www.youtube.com/watch?v={video_id}"
                                views = int(video["statistics"]["viewCount"])

                                # No view threshold, all videos will be considered viral
                                video_details.append({
                                    "Title": title,
                                    "URL": video_url,
                                    "Views": views,
                                })

                            # Add to final results if there are videos
                            if video_details:
                                all_results.append({
                                    "Channel Name": channel_name,
                                    "Channel URL": channel_url,
                                    "Subscribers": subs,
                                    "Videos": video_details,
                                })

        # Display results
        if all_results:
            st.success(f"Found {len(all_results)} newly launched viral channels!")
            for result in all_results:
                st.markdown(f"### {result['Channel Name']}")
                st.markdown(f"**Subscribers:** {result['Subscribers']}")
                st.markdown(f"[Visit Channel]({result['Channel URL']})")
                st.write("**Top 5 Videos:**")
                for video in result["Videos"]:
                    st.markdown(f"- **{video['Title']}**: [Watch Here]({video['URL']}) - Views: {video['Views']}")
                st.write("---")
        else:
            st.warning("No viral videos found for channels matching the selected filters.")

    except Exception as e:
        st.error(f"An error occurred: {e}")
