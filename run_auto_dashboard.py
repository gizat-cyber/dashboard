#!/usr/bin/env python3
"""
Launch script for Auto-Loading Fleet Management Dashboard
"""

import subprocess
import sys
import os

def main():
    """Launch the Auto-Loading Fleet Management Dashboard"""
    print("🚀 Starting Auto-Loading Fleet Management Dashboard...")
    
    # Check if the auto dashboard file exists
    if not os.path.exists("fleet_dashboard_auto.py"):
        print("❌ fleet_dashboard_auto.py not found!")
        return
    
    # Check .env file
    if not os.path.exists(".env"):
        print("⚠️  .env file not found!")
        print("Create a .env file with the following content:")
        print("SAMSARA_API_TOKEN=your_token_here")
        print("")
        print("You can still run the dashboard and enter the token manually in the sidebar.")
        print("")
        
    try:
        # Launch Streamlit with the auto-loading dashboard
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "fleet_dashboard_auto.py", 
            "--server.port", "8501",
            "--server.address", "localhost",
            "--browser.gatherUsageStats", "false"
        ], check=True)
        
    except KeyboardInterrupt:
        print("\n🛑 Dashboard stopped by user")
    except Exception as e:
        print(f"❌ Launch error: {e}")

if __name__ == "__main__":
    main()
