import google.generativeai as genai
genai.configure(api_key='AIzaSyBgun5qwVjfnSfnMNRTcRiM9BlmCl081yQ')
model = genai.GenerativeModel(model_name="models/gemini-2.0-pro-exp")
response = model.generate_content("Resuma isso: O Brasil é um país tropical")
print(response.text)

