import streamlit as st
import requests
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import re
from collections import Counter

# YouTube API Configuration
API_KEY = "AIzaSyAMSPSOQaPGAia_SxtMzcsL72w-cuSgh9U"
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels"

# Initialize Session State
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'search_completed' not in st.session_state:
    st.session_state.search_completed = False
if 'similarity_analysis' not in st.session_state:
    st.session_state.similarity_analysis = False

# Page Configuration
st.set_page_config(page_title="YouTube Research Tool", page_icon="🔍", layout="wide")
st.title("🔍 YouTube Channel Research Tool")
st.markdown("**Discover new YouTube channels based on your custom criteria**")

# ============================================
# SIMILARITY DETECTION FUNCTIONS
# ============================================

def calculate_text_similarity(text1, text2):
    """Calculate similarity ratio between two texts (0-1)"""
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

def extract_keywords(text, top_n=10):
    """Extract important keywords from text"""
    # Remove common words
    common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                    'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
                    'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
                    'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
                    'i', 'you', 'he', 'she', 'it', 'we', 'they', 'my', 'your', 'his', 'her'}
    
    # Extract words
    words = re.findall(r'\b[a-z]+\b', text.lower())
    filtered_words = [w for w in words if w not in common_words and len(w) > 3]
    
    # Get most common
    word_freq = Counter(filtered_words)
    return [word for word, _ in word_freq.most_common(top_n)]

def calculate_keyword_overlap(keywords1, keywords2):
    """Calculate overlap between two keyword lists"""
    if not keywords1 or not keywords2:
        return 0
    set1, set2 = set(keywords1), set(keywords2)
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0

def find_similar_videos(target_video, all_videos, threshold=0.3):
    """Find videos similar to the target video"""
    similar = []
    target_title = target_video['video_title']
    target_desc = target_video.get('description', '')
    target_keywords = extract_keywords(target_title + ' ' + target_desc)
    
    for video in all_videos:
        if video['video_url'] == target_video['video_url']:
            continue
        
        # Calculate multiple similarity scores
        title_sim = calculate_text_similarity(target_title, video['video_title'])
        
        video_keywords = extract_keywords(video['video_title'] + ' ' + video.get('description', ''))
        keyword_sim = calculate_keyword_overlap(target_keywords, video_keywords)
        
        # Combined similarity score
        similarity_score = (title_sim * 0.6) + (keyword_sim * 0.4)
        
        if similarity_score >= threshold:
            similar.append({
                'video': video,
                'similarity_score': similarity_score,
                'title_similarity': title_sim,
                'keyword_similarity': keyword_sim
            })
    
    # Sort by similarity score
    similar.sort(key=lambda x: x['similarity_score'], reverse=True)
    return similar

def group_similar_content(all_videos, threshold=0.35):
    """Group videos into clusters of similar content"""
    clusters = []
    processed = set()
    
    for i, video in enumerate(all_videos):
        if i in processed:
            continue
        
        # Start a new cluster
        cluster = [video]
        processed.add(i)
        
        # Find similar videos
        for j, other_video in enumerate(all_videos):
            if j in processed or i == j:
                continue
            
            # Calculate similarity
            title_sim = calculate_text_similarity(video['video_title'], other_video['video_title'])
            
            video_keywords = extract_keywords(video['video_title'])
            other_keywords = extract_keywords(other_video['video_title'])
            keyword_sim = calculate_keyword_overlap(video_keywords, other_keywords)
            
            combined_sim = (title_sim * 0.6) + (keyword_sim * 0.4)
            
            if combined_sim >= threshold:
                cluster.append(other_video)
                processed.add(j)
        
        clusters.append(cluster)
    
    # Sort clusters by size (largest first)
    clusters.sort(key=len, reverse=True)
    return clusters

def detect_trending_topics(all_videos, min_occurrence=2):
    """Detect trending topics across all videos"""
    all_keywords = []
    
    for video in all_videos:
        keywords = extract_keywords(video['video_title'])
        all_keywords.extend(keywords)
    
    # Count keyword frequency
    keyword_freq = Counter(all_keywords)
    trending = [(word, count) for word, count in keyword_freq.most_common(20) 
                if count >= min_occurrence]
    
    return trending

# ============================================
# SIDEBAR - INPUT PARAMETERS
# ============================================
st.sidebar.header("⚙️ Search Configuration")

# 1. KEYWORD INPUT (User-Defined)
st.sidebar.subheader("1️⃣ Keywords")
keywords_input = st.sidebar.text_area(
    "Enter Keywords (one per line):",
    value="Reddit Stories\nCheating Stories\nRelationship Advice",
    height=150,
    help="Enter one keyword per line to search for relevant videos"
)
keywords = [k.strip() for k in keywords_input.split('\n') if k.strip()]

# 2. TIME RANGE FILTER (User-Defined)
st.sidebar.subheader("2️⃣ Video Upload Time")
time_range = st.sidebar.selectbox(
    "Videos uploaded within:",
    ["Last 24 Hours", "Last 7 Days", "Last 30 Days", "Last 3 Months", 
     "Last 6 Months", "Last Year", "Custom Days"]
)

custom_days = None
if time_range == "Custom Days":
    custom_days = st.sidebar.number_input("Enter Days:", min_value=1, max_value=365, value=30)

# 3. SUBSCRIBER COUNT FILTER (User-Defined Range)
st.sidebar.subheader("3️⃣ Channel Subscribers")
enable_sub_filter = st.sidebar.checkbox("Enable Subscriber Filter", value=True)

if enable_sub_filter:
    col1, col2 = st.sidebar.columns(2)
    with col1:
        min_subs = st.number_input("Min:", min_value=0, value=0, step=100)
    with col2:
        max_subs = st.number_input("Max:", min_value=0, value=5000, step=100)
else:
    min_subs, max_subs = 0, float('inf')

# 4. CHANNEL AGE FILTER (User-Defined)
st.sidebar.subheader("4️⃣ Channel Age")
enable_age_filter = st.sidebar.checkbox("Enable Channel Age Filter", value=True)

if enable_age_filter:
    age_range = st.sidebar.selectbox(
        "Channel created within:",
        ["Last 30 Days", "Last 3 Months", "Last 6 Months", 
         "Last Year", "Last 2 Years", "Custom Days"]
    )
    
    custom_age_days = None
    if age_range == "Custom Days":
        custom_age_days = st.sidebar.number_input(
            "Enter Days (Age):", 
            min_value=1, 
            max_value=3650, 
            value=365
        )
else:
    age_range = None

# 5. RESULTS PER KEYWORD
st.sidebar.subheader("5️⃣ Results")
max_results = st.sidebar.slider("Max results per keyword:", 1, 50, 10)

# 6. SIMILARITY DETECTION
st.sidebar.subheader("6️⃣ Similarity Analysis")
enable_similarity = st.sidebar.checkbox("Enable Similarity Detection", value=True, 
                                        help="Find and group similar content")
if enable_similarity:
    similarity_threshold = st.sidebar.slider(
        "Similarity Threshold:",
        min_value=0.1,
        max_value=0.9,
        value=0.35,
        step=0.05,
        help="Higher = stricter matching (0.3-0.4 recommended)"
    )

# SEARCH BUTTON
st.sidebar.markdown("---")
search_btn = st.sidebar.button("🔍 Start Research", type="primary", use_container_width=True)

# CLEAR RESULTS BUTTON
if st.session_state.search_completed:
    if st.sidebar.button("🗑️ Clear Results", use_container_width=True):
        st.session_state.search_results = []
        st.session_state.search_completed = False
        st.session_state.similarity_analysis = False
        st.rerun()

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_published_after_date(option, custom=None):
    """Calculate the publishedAfter date for video search"""
    now = datetime.utcnow()
    time_map = {
        "Last 24 Hours": timedelta(hours=24),
        "Last 7 Days": timedelta(days=7),
        "Last 30 Days": timedelta(days=30),
        "Last 3 Months": timedelta(days=90),
        "Last 6 Months": timedelta(days=180),
        "Last Year": timedelta(days=365),
    }
    
    if option == "Custom Days" and custom:
        delta = timedelta(days=custom)
    else:
        delta = time_map.get(option, timedelta(days=30))
    
    return (now - delta).isoformat("T") + "Z"

def get_channel_age_cutoff(option, custom=None):
    """Calculate the channel creation date cutoff"""
    if not option:
        return None
    
    now = datetime.utcnow()
    age_map = {
        "Last 30 Days": timedelta(days=30),
        "Last 3 Months": timedelta(days=90),
        "Last 6 Months": timedelta(days=180),
        "Last Year": timedelta(days=365),
        "Last 2 Years": timedelta(days=730),
    }
    
    if option == "Custom Days" and custom:
        delta = timedelta(days=custom)
    else:
        delta = age_map.get(option, timedelta(days=365))
    
    return now - delta

def calculate_channel_age(created_date_str):
    """Calculate channel age in days"""
    try:
        created = datetime.strptime(created_date_str, "%Y-%m-%dT%H:%M:%SZ")
        age_days = (datetime.utcnow() - created).days
        return age_days, created
    except:
        return None, None

def perform_search(keywords, published_after, channel_age_cutoff, enable_age_filter, 
                   enable_sub_filter, min_subs, max_subs, max_results, API_KEY):
    """Perform the YouTube search and return results"""
    all_results = []
    progress = st.progress(0)
    status = st.empty()
    
    # Search each keyword
    total = len(keywords)
    for idx, keyword in enumerate(keywords):
        status.text(f"🔎 Searching: {keyword} ({idx+1}/{total})")
        progress.progress((idx+1)/total)
        
        # API Search Request
        search_params = {
            "part": "snippet",
            "q": keyword,
            "type": "video",
            "order": "date",
            "publishedAfter": published_after,
            "maxResults": max_results,
            "key": API_KEY
        }
        
        response = requests.get(YOUTUBE_SEARCH_URL, params=search_params)
        data = response.json()
        
        # Check for errors
        if "error" in data:
            st.error(f"API Error: {data['error']['message']}")
            continue
        
        if "items" not in data or not data["items"]:
            continue
        
        videos = data["items"]
        video_ids = [v["id"]["videoId"] for v in videos if "videoId" in v.get("id", {})]
        channel_ids = list(set([v["snippet"]["channelId"] for v in videos if "snippet" in v]))
        
        if not video_ids or not channel_ids:
            continue
        
        # Fetch Video Statistics
        stats_response = requests.get(
            YOUTUBE_VIDEO_URL,
            params={"part": "statistics,snippet", "id": ",".join(video_ids), "key": API_KEY}
        )
        stats_data = stats_response.json()
        
        # Fetch Channel Information (with creation date)
        channel_response = requests.get(
            YOUTUBE_CHANNEL_URL,
            params={"part": "statistics,snippet", "id": ",".join(channel_ids), "key": API_KEY}
        )
        channel_data = channel_response.json()
        
        if "items" not in stats_data or "items" not in channel_data:
            continue
        
        # Build lookup dictionaries
        channel_info = {}
        for ch in channel_data["items"]:
            ch_id = ch["id"]
            subs = int(ch["statistics"].get("subscriberCount", 0))
            created = ch["snippet"].get("publishedAt", "")
            age_days, created_dt = calculate_channel_age(created)
            
            channel_info[ch_id] = {
                "name": ch["snippet"].get("title", "N/A"),
                "subscribers": subs,
                "created": created,
                "age_days": age_days,
                "created_dt": created_dt
            }
        
        video_stats = {}
        for v in stats_data["items"]:
            video_stats[v["id"]] = {
                "views": int(v["statistics"].get("viewCount", 0)),
                "likes": int(v["statistics"].get("likeCount", 0)),
                "comments": int(v["statistics"].get("commentCount", 0)),
                "description": v["snippet"].get("description", "")[:300],
                "tags": v["snippet"].get("tags", [])
            }
        
        # Process and filter results
        for video in videos:
            vid_id = video["id"].get("videoId")
            ch_id = video["snippet"]["channelId"]
            
            if not vid_id or ch_id not in channel_info or vid_id not in video_stats:
                continue
            
            ch = channel_info[ch_id]
            
            # Apply subscriber filter
            if enable_sub_filter:
                if ch["subscribers"] < min_subs or ch["subscribers"] > max_subs:
                    continue
            
            # Apply channel age filter
            if enable_age_filter and channel_age_cutoff and ch["created_dt"]:
                if ch["created_dt"] < channel_age_cutoff:
                    continue
            
            # Add to results
            all_results.append({
                "keyword": keyword,
                "video_title": video["snippet"].get("title", "N/A"),
                "channel_name": ch["name"],
                "video_url": f"https://www.youtube.com/watch?v={vid_id}",
                "channel_url": f"https://www.youtube.com/channel/{ch_id}",
                "views": video_stats[vid_id]["views"],
                "likes": video_stats[vid_id]["likes"],
                "comments": video_stats[vid_id]["comments"],
                "description": video_stats[vid_id]["description"],
                "tags": video_stats[vid_id]["tags"],
                "subscribers": ch["subscribers"],
                "channel_age_days": ch["age_days"] if ch["age_days"] else "N/A",
                "published": video["snippet"].get("publishedAt", "N/A")[:10]
            })
    
    # Clear progress
    progress.empty()
    status.empty()
    
    return all_results

# ============================================
# MAIN CONTENT AREA
# ============================================

# If search button is clicked, perform new search
if search_btn:
    if not keywords:
        st.error("❌ Please enter at least one keyword!")
    elif API_KEY == "Enter your API Key here":
        st.error("❌ Please add your YouTube API Key!")
    else:
        try:
            # Calculate date filters
            published_after = get_published_after_date(time_range, custom_days)
            channel_age_cutoff = get_channel_age_cutoff(age_range, custom_age_days) if enable_age_filter else None
            
            # Perform search and store in session state
            st.session_state.search_results = perform_search(
                keywords, published_after, channel_age_cutoff, enable_age_filter,
                enable_sub_filter, min_subs, max_subs, max_results, API_KEY
            )
            st.session_state.search_completed = True
            st.session_state.similarity_analysis = enable_similarity
            
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.exception(e)

# Display results from session state
if st.session_state.search_completed and st.session_state.search_results:
    all_results = st.session_state.search_results
    
    st.success(f"✅ Found **{len(all_results)}** videos from **{len(set([r['channel_name'] for r in all_results]))}** unique channels!")
    
    # Summary Stats
    st.subheader("📊 Summary Statistics")
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric("Total Videos", len(all_results))
    col2.metric("Unique Channels", len(set([r['channel_name'] for r in all_results])))
    col3.metric("Total Views", f"{sum([r['views'] for r in all_results]):,}")
    col4.metric("Avg Subscribers", f"{int(sum([r['subscribers'] for r in all_results])/len(all_results)):,}")
    
    # ============================================
    # SIMILARITY ANALYSIS SECTION
    # ============================================
    if st.session_state.similarity_analysis and enable_similarity:
        st.markdown("---")
        st.header("🔗 Similarity Analysis")
        
        tab1, tab2, tab3 = st.tabs(["📊 Trending Topics", "🎯 Content Clusters", "🔍 Find Similar"])
        
        # TAB 1: Trending Topics
        with tab1:
            st.subheader("🔥 Trending Topics Across Results")
            trending = detect_trending_topics(all_results, min_occurrence=2)
            
            if trending:
                cols = st.columns(4)
                for idx, (topic, count) in enumerate(trending[:12]):
                    with cols[idx % 4]:
                        st.metric(topic.title(), f"{count} videos", delta=None)
            else:
                st.info("No trending topics detected")
        
        # TAB 2: Content Clusters
        with tab2:
            st.subheader("🎯 Similar Content Groups")
            clusters = group_similar_content(all_results, threshold=similarity_threshold)
            
            # Only show clusters with more than 1 video
            significant_clusters = [c for c in clusters if len(c) > 1]
            
            if significant_clusters:
                st.write(f"Found **{len(significant_clusters)}** groups of similar content:")
                
                for i, cluster in enumerate(significant_clusters[:10], 1):  # Show top 10 clusters
                    with st.expander(f"📁 Cluster {i} - {len(cluster)} similar videos"):
                        for video in cluster:
                            st.markdown(f"- [{video['video_title']}]({video['video_url']}) | "
                                      f"👁️ {video['views']:,} | 👥 {video['subscribers']:,} subs")
            else:
                st.info("No significant content clusters found. Try lowering the similarity threshold.")
        
        # TAB 3: Find Similar
        with tab3:
            st.subheader("🔍 Find Similar Videos")
            
            # Create a searchable list
            video_options = [f"{r['video_title'][:60]}... ({r['views']:,} views)" 
                           for r in all_results]
            
            selected_video_idx = st.selectbox(
                "Select a video to find similar content:",
                range(len(all_results)),
                format_func=lambda x: video_options[x]
            )
            
            if st.button("Find Similar Videos"):
                target = all_results[selected_video_idx]
                similar = find_similar_videos(target, all_results, threshold=similarity_threshold)
                
                if similar:
                    st.success(f"Found {len(similar)} similar videos:")
                    
                    for sim in similar[:10]:  # Show top 10
                        v = sim['video']
                        score = sim['similarity_score']
                        
                        with st.container():
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.markdown(f"**[{v['video_title']}]({v['video_url']})**")
                                st.caption(f"Channel: {v['channel_name']} | {v['views']:,} views")
                            with col2:
                                st.metric("Match", f"{score*100:.0f}%")
                            st.markdown("---")
                else:
                    st.warning("No similar videos found. Try lowering the similarity threshold.")
    
    # ============================================
    # STANDARD RESULTS DISPLAY
    # ============================================
    st.markdown("---")
    st.subheader("📋 All Results")
    
    # Sort Options
    sort_option = st.selectbox(
        "Sort by:",
        ["Views (High to Low)", "Subscribers (Low to High)", 
         "Channel Age (Newest)", "Published Date (Recent)",
         "Engagement Rate (High to Low)"]
    )
    
    # Create a copy for sorting
    sorted_results = all_results.copy()
    
    if "Views (High" in sort_option:
        sorted_results.sort(key=lambda x: x["views"], reverse=True)
    elif "Subscribers (Low" in sort_option:
        sorted_results.sort(key=lambda x: x["subscribers"])
    elif "Channel Age" in sort_option:
        sorted_results.sort(key=lambda x: x["channel_age_days"] if isinstance(x["channel_age_days"], int) else 999999)
    elif "Engagement Rate" in sort_option:
        # Calculate engagement rate (likes + comments / views)
        sorted_results.sort(key=lambda x: (x["likes"] + x["comments"]) / max(x["views"], 1), reverse=True)
    else:
        sorted_results.sort(key=lambda x: x["published"], reverse=True)
    
    # Display Results
    for i, r in enumerate(sorted_results, 1):
        with st.expander(f"#{i} - {r['video_title'][:70]}..."):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"**🎥 Video:** [{r['video_title']}]({r['video_url']})")
                st.markdown(f"**📺 Channel:** [{r['channel_name']}]({r['channel_url']})")
                st.markdown(f"**🔑 Keyword:** {r['keyword']}")
                st.markdown(f"**📅 Published:** {r['published']}")
                
                if r.get('description'):
                    st.caption(f"📝 {r['description'][:150]}...")
                
                if r.get('tags'):
                    tags_str = ", ".join(r['tags'][:5])
                    st.caption(f"🏷️ Tags: {tags_str}")
            
            with col2:
                st.metric("👁️ Views", f"{r['views']:,}")
                st.metric("👍 Likes", f"{r['likes']:,}")
                st.metric("💬 Comments", f"{r['comments']:,}")
                engagement = (r['likes'] + r['comments']) / max(r['views'], 1) * 100
                st.metric("📈 Engagement", f"{engagement:.2f}%")
                st.metric("👥 Subscribers", f"{r['subscribers']:,}")
                st.metric("⏱️ Channel Age", 
                         f"{r['channel_age_days']} days" if isinstance(r['channel_age_days'], int) else "N/A")
    
    # ============================================
    # EXPORT SECTION
    # ============================================
    st.markdown("---")
    st.subheader("📥 Export Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Export All Results
        import io
        csv = io.StringIO()
        csv.write("Keyword,Video Title,Channel Name,Subscribers,Views,Likes,Comments,Engagement Rate,Channel Age (Days),Published Date,Video URL,Channel URL\n")
        for r in sorted_results:
            video_title = r['video_title'].replace(',', ';').replace('\n', ' ')
            channel_name = r['channel_name'].replace(',', ';')
            engagement = (r['likes'] + r['comments']) / max(r['views'], 1) * 100
            csv.write(f"{r['keyword']},{video_title},{channel_name},{r['subscribers']},{r['views']},{r['likes']},{r['comments']},{engagement:.2f}%,{r['channel_age_days']},{r['published']},{r['video_url']},{r['channel_url']}\n")
        
        st.download_button(
            "📥 Download All Results (CSV)",
            data=csv.getvalue(),
            file_name=f"youtube_research_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    with col2:
        # Export Similarity Analysis
        if st.session_state.similarity_analysis and enable_similarity:
            clusters = group_similar_content(all_results, threshold=similarity_threshold)
            cluster_csv = io.StringIO()
            cluster_csv.write("Cluster ID,Video Title,Views,Subscribers,Video URL\n")
            
            for i, cluster in enumerate(clusters, 1):
                for video in cluster:
                    title = video['video_title'].replace(',', ';').replace('\n', ' ')
                    cluster_csv.write(f"{i},{title},{video['views']},{video['subscribers']},{video['video_url']}\n")
            
            st.download_button(
                "📥 Download Clusters (CSV)",
                data=cluster_csv.getvalue(),
                file_name=f"youtube_clusters_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

elif st.session_state.search_completed and not st.session_state.search_results:
    st.warning("⚠️ No results found. Try adjusting your filters.")

else:
    # Display current configuration
    st.info("👈 Configure your search parameters in the sidebar and click **Start Research**")
    
    st.subheader("📋 Current Configuration:")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write(f"**Keywords:** {len(keywords)}")
        st.write(f"**Time Range:** {time_range}")
    
    with col2:
        if enable_sub_filter:
            st.write(f"**Subscribers:** {min_subs:,} - {max_subs:,}")
        else:
            st.write(f"**Subscribers:** Any")
    
    with col3:
        if enable_age_filter:
            st.write(f"**Channel Age:** {age_range}")
        else:
            st.write(f"**Channel Age:** Any")

# Footer
st.sidebar.markdown("---")
st.sidebar.info("💡 **Tip:** Enable Similarity Detection to find content clusters and trending topics!")
