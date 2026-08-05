from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
import os
from dotenv import load_dotenv

load_dotenv()

class LLMFactory:
    @staticmethod
    def get_llm(provider: str, temperature: float = 0.0):
        provider = provider.lower()
        
        if provider == "openai":
            return ChatOpenAI(
                model_name=os.getenv("MODEL_NAME", "gpt-4o"), 
                temperature=temperature,
                api_key=os.getenv("OPENAI_API_KEY")
            )
        elif provider == "gemini":
            return ChatGoogleGenerativeAI(
                model=os.getenv("MODEL_NAME", "gemini-1.5-pro"), 
                temperature=temperature,
                google_api_key=os.getenv("GOOGLE_API_KEY")
            )
        elif provider == "claude":
            return ChatAnthropic(
                model_name=os.getenv("MODEL_NAME", "claude-3-5-sonnet-20240620"), 
                temperature=temperature,
                anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
            )
        else:
            raise ValueError(f"지원하지 않는 LLM 제공자입니다: {provider}")