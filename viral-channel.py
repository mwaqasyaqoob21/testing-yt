import streamlit as st
import requests
from datetime import datetime, timedelta

# YouTube API Key
API_KEY = "AIzaSyDJcigV37FRMhkO73M97OUm85tb82y6HM0"  # Enter your API Key here
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels"

# Streamlit App Title
st.title("YouTube Viral Topics Tool")

# Input Fields
days = st.number_input("Enter Days to Search (1-30):", min_value=1, max_value=30, value=5)
topic = st.text_input("Enter a topic to search channels:", "")

# Fetch Data Button
if st.button("Fetch Data"):
    if not topic:
        st.warning("Please enter a topic to search.")
    else:
        try:
            # Calculate date range
            start_date = (datetime.utcnow() - timedelta(days=int(days))).isoformat("T") + "Z"
            all_results = []

            # Define search parameters for videos based on the topic
            search_params = {
                "part": "snippet",
                "q": topic,
                "type": "video",
                "order": "viewCount",  # Sort by most viewed
                "publishedAfter": start_date,
                "maxResults": 5,  # Get up to 5 videos
                "key": API_KEY,
            }

            # Fetch video data based on topic
            response = requests.get(YOUTUBE_SEARCH_URL, params=search_params)
            data = response.json()

            # Check if "items" key exists and process the results
            if "items" not in data or not data["items"]:
                st.warning(f"No videos found for topic: {topic}.")
            else:
                video_ids = [video["id"]["videoId"] for video in data["items"]]
                channel_ids = [video["snippet"]["channelId"] for video in data["items"]]

                # Fetch video statistics
                stats_params = {"part": "statistics", "id": ",".join(video_ids), "key": API_KEY}
                stats_response = requests.get(YOUTUBE_VIDEO_URL, params=stats_params)
                stats_data = stats_response.json()

                # Fetch channel statistics
                channel_params = {"part": "statistics", "id": ",".join(channel_ids), "key": API_KEY}
                channel_response = requests.get(YOUTUBE_CHANNEL_URL, params=channel_params)
                channel_data = channel_response.json()

                # Check if we have valid statistics and channels data
                if "items" not in stats_data or not stats_data["items"] or "items" not in channel_data or not channel_data["items"]:
                    st.warning("Failed to fetch video or channel statistics.")
                else:
                    stats = stats_data["items"]
                    channels = channel_data["items"]

                    # Process and filter results for videos
                    for video, stat, channel in zip(data["items"], stats, channels):
                        title = video["snippet"].get("title", "N/A")
                        description = video["snippet"].get("description", "")[:200]  # Limit description to 200 chars
                        video_url = f"https://www.youtube.com/watch?v={video['id']['videoId']}"
                        views = int(stat["statistics"].get("viewCount", 0))
                        subs = int(channel["statistics"].get("subscriberCount", 0))

                        # No filter on subscribers (or broaden the range if needed)
                        all_results.append({
                            "Title": title,
                            "Description": description,
                            "URL": video_url,
                            "Views": views,
                            "Subscribers": subs,
                        })

            # Display results
            if all_results:
                st.success(f"Found {len(all_results)} viral videos across all topics!")
                for result in all_results:
                    st.markdown(f"**Title:** {result['Title']}  \n"
                                f"**Description:** {result['Description']}  \n"
                                f"**URL:** [Watch Video]({result['URL']})  \n"
                                f"**Views:** {result['Views']}  \n"
                                f"**Subscribers:** {result['Subscribers']}")
                    st.write("---")
            else:
                st.warning("No results found for the given filters.")

        except Exception as e:
            st.error(f"An error occurred: {e}")
