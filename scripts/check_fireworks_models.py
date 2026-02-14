"""Check available Fireworks AI models with serverless and function calling support.

Run this to see which models you have access to and can use with Cecil AI.
"""

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


def fetch_available_models():
    """Fetch models from Fireworks API that support serverless + tools."""
    api_key = os.getenv("FIREWORKS_API_KEY")
    
    if not api_key:
        print("❌ FIREWORKS_API_KEY not found in .env file")
        print("Please add your Fireworks API key to .env:")
        print("FIREWORKS_API_KEY=your_key_here")
        sys.exit(1)
    
    # Fireworks uses "fireworks" as the account_id for their models
    account_id = "fireworks"
    url = f"https://api.fireworks.ai/v1/accounts/{account_id}/models"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    params = {
        "pageSize": 200
    }
    
    print(f"🔍 Fetching available models from Fireworks AI...\n")
    
    try:
        response = httpx.get(url, headers=headers, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        
        models = data.get("models", [])
        
        print(f"✅ Found {len(models)} models\n")
        print("=" * 100)
        print(f"{'MODEL NAME':<60} {'SERVERLESS':<12} {'TOOLS':<8} {'CONTEXT':<8}")
        print("=" * 100)
        
        # Group by use case
        general_models = []
        coder_models = []
        
        for model in models:
            name = model.get("name", "").replace(f"accounts/{account_id}/models/", "")
            serverless = "✓" if model.get("supportsServerless") else "✗"
            tools = "✓" if model.get("supportsTools") else "✗"
            context = model.get("contextLength", "N/A")
            
            # Skip if no serverless or tools support
            if not model.get("supportsServerless") or not model.get("supportsTools"):
                continue
            
            if "coder" in name.lower() or "qwen" in name.lower() or "deepseek" in name.lower():
                coder_models.append((name, serverless, tools, context))
            else:
                general_models.append((name, serverless, tools, context))
        
        print("\n📊 GENERAL PURPOSE MODELS (for PM, Researcher, Analyst):")
        print("-" * 100)
        for name, serverless, tools, context in general_models[:10]:
            print(f"{name:<60} {serverless:<12} {tools:<8} {context:<8}")
        
        print("\n💻 CODING MODELS (for Software Developer):")
        print("-" * 100)
        for name, serverless, tools, context in coder_models[:10]:
            print(f"{name:<60} {serverless:<12} {tools:<8} {context:<8}")
        
        print("\n" + "=" * 100)
        print("\n✨ RECOMMENDED CONFIGURATION for providers.py:\n")
        
        if general_models:
            best_general = general_models[0][0]
            print(f'    default_model="accounts/fireworks/models/{best_general}",')
        
        if coder_models:
            best_coder = coder_models[0][0]
            print(f'\n    "software_developer": {{')
            print(f'        "fireworks": "accounts/fireworks/models/{best_coder}",')
            print(f'    }},')
        
        print("\n")
        return general_models, coder_models
        
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP Error: {e.response.status_code}")
        print(f"   Response: {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    fetch_available_models()
