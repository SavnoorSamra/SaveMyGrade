from google import genai

client = genai.Client(api_key="AIzaSyAGRv7AC7bWxxs3_89TfInd-vPqf2jgAWs")

response = client.models.generate_content(
    model="gemini-3-flash-preview", contents="Briefly explain the concept of photosynthesis."
)
print(response.text)