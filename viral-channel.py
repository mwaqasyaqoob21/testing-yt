import streamlit as st
import requests
from datetime import datetime, timedelta

# YouTube API Key
API_KEY = "AIzaSyDJcigV37FRMhkO73M97OUm85tb82y6HM0"  # Enter your API Key here
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels"

# Streamlit App Title
st.title("YouTube Channel Discovery Tool")

# Input Fields
topic = st.text_input("Enter a topic to search channels:", "")

# Subscriber range inputs
min_subs = st.number_input("Enter Minimum Subscriber Count:", min_value=0, max_value=1000000, value=0)
max_subs = st.number_input("Enter Maximum Subscriber Count:", min_value=0, max_value=1000000, value=5000)

# Time Period Dropdown (7 days, 14 days, 28 days)
time_period = st.selectbox("Select Time Period", ["7 Days", "14 Days", "28 Days"])

# Fetch Data Button
if st.button("Fetch Data"):
    if not topic:
        st.warning("Please enter a topic to search.")
    else:
        try:
            # Set date range based on selected time period
            if time_period == "7 Days":
                start_date = (datetime.utcnow() - timedelta(days=7)).isoformat("T") + "Z"
            elif time_period == "14 Days":
                start_date = (datetime.utcnow() - timedelta(days=14)).isoformat("T") + "Z"
            else:
                start_date = (datetime.utcnow() - timedelta(days=28)).isoformat("T") + "Z"
            
            all_results = []

            # Define search parameters for videos based on the topic
            search_params = {
                "part": "snippet",
                "q": topic,  # Search for videos related to the selected topic
                "type": "video",
                "publishedAfter": start_date,  # Filter by the selected time period
                "maxResults": 10,  # Get up to 10 videos
                "key": API_KEY,
            }

            # Fetch video data based on topic
            response = requests.get(YOUTUBE_SEARCH_URL, params=search_params)
            data = response.json()

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
                channel_params = {"part": "statistics,snippet", "id": ",".join(channel_ids), "key": API_KEY}
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

                        # Handle missing channel title and category
                        channel_name = channel["snippet"].get("channelTitle", "N/A")
                        country = channel["snippet"].get("country", "N/A")  # Country (if available)
                        channel_category = channel["snippet"].get("categoryId", "N/A")  # Niche/Category

                        # Calculate virality: views to subscribers ratio
                        virality_index = views / (subs if subs != 0 else 1)

                        # Apply filters for channels with specified subscriber count and viral videos
                        if min_subs <= subs <= max_subs and virality_index > 1:  # Assuming virality index greater than 1 is "viral"
                            channel_age = (datetime.utcnow() - datetime.strptime(channel["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ")).days

                            all_results.append({
                                "Channel Name": channel_name,
                                "Channel URL": f"https://www.youtube.com/channel/{channel['id']}",
                                "Subscribers": subs,
                                "Age (Days)": channel_age,
                                "Country": country,
                                "Niche": channel_category,
                                "Top Video": title,
                                "Video URL": video_url,
                                "Views": views,
                            })

            # Display results
            if all_results:
                st.success(f"Found {len(all_results)} viral channels matching your filters!")
                for result in all_results:
                    st.markdown(f"### {result['Channel Name']}")
                    st.markdown(f"**Subscribers:** {result['Subscribers']}")
                    st.markdown(f"**Age:** {result['Age (Days)']} days")
                    st.markdown(f"**Country:** {result['Country']}")
                    st.markdown(f"**Niche:** {result['Niche']}")
                    st.markdown(f"**Top Video:** [{result['Top Video']}]({result['Video URL']}) - Views: {result['Views']}")
                    st.markdown(f"[Visit Channel]({result['Channel URL']})")
                    st.write("---")
            else:
                st.warning("No channels found matching the selected filters.")

        except Exception as e:
            st.error(f"An error occurred: {e}")
