import os
import re
import json
from collections import defaultdict

from sklearn.feature_extraction.text import TfidfVectorizer as TfidfVectoriser
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
from firebase_admin import firestore, initialize_app

# global env is overwriting our local google application credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "service_account.json"

initialize_app()
db = firestore.client()

# Globals
# Load the stop words
nltk.download('punkt')
nltk.download('wordnet')
nltk.download('stopwords')

lemmatizer = WordNetLemmatizer()
stop_words = set(stopwords.words('english'))

def get_files():
    # Find the docs for vectorisation
    # They should be in the CONTENT folder
    for_vectorisation = {}
    for root, dirs, files in os.walk("CONTENT"):
        if files:
            for file in files:
                if file.endswith(".md"):
                    with open(os.path.join(root, file), "r") as f:
                        for_vectorisation[os.path.join(root, file)] = f.read()

    return for_vectorisation

def clean_doc_name(doc_name):
    # Remove the CONTENT/ prefix and the .md suffix
    return doc_name.replace("CONTENT/", "")

def preprocess_text(text):
    # Preprocess the text
    # Lowercase the text
    text = text.lower()
    # Remove punctuation and numbers
    text = re.sub(r'\W+', ' ', text)
    # Tokenize the text
    tokens = word_tokenize(text)
    # Remove stop words and lemmatize tokens
    tokens = [lemmatizer.lemmatize(token) for token in tokens if token not in stop_words]
    return ' '.join(tokens)

class CustomVectoriser(TfidfVectoriser):
    def __init__(self):
        super().__init__()

    def build_preprocessor(self):
        preprocessing_fn = super().build_preprocessor()
        return lambda doc: preprocess_text(preprocessing_fn(doc))

    def fit_transform(self, raw_documents, y=None):
        processed_documents = [preprocess_text(doc) for doc in raw_documents.values()]
        return super().fit_transform(processed_documents, y)

    def transform(self, raw_documents):
        processed_documents = [preprocess_text(doc) for doc in raw_documents.values()]
        return super().transform(processed_documents)

    def fit(self, raw_documents, y=None):
        processed_documents = [preprocess_text(doc) for doc in raw_documents.values()]
        return super().fit(processed_documents, y)


def vectorise_docs(for_vectorisation):
    # Vectorise the docs
    vectoriser = CustomVectoriser()
    vectors = vectoriser.fit_transform(for_vectorisation)

    return vectors

def calculate_similarity(vectors):
    # Calculate the similarity between the vectors
    similarity_matrix = cosine_similarity(vectors, vectors)
    return similarity_matrix

def get_recommendations(similarity_matrix, for_vectorisation, num_recs=6):
    # Get the recommendations
    recommendations = defaultdict(list)
    for i, doc in enumerate(for_vectorisation):
        print(f"Getting recommendations for {doc}")
        recs = similarity_matrix[i].argsort()[-(1 + num_recs):-1]
        clean_name = clean_doc_name(doc)
        for r in recs:
            recommendations[clean_name].append(clean_doc_name(list(for_vectorisation.keys())[r]))

    return recommendations

def update_firestore(recommendations):
    try:
        doc_ref = db.collection('recommendations').document('recommendations')
        doc_ref.set(recommendations)
        print("Recommendations updated in Firestore")
    except Exception as e:
        print(f"Error updating Firestore: {e}")

def main():
    # This script is expected to be run from the root of the project
    # E.g. python content_management/generate_recommendations.py
    for_vectorisation = get_files()

    X = vectorise_docs(for_vectorisation)

    similarity_matrix = calculate_similarity(X)

    recommendations = get_recommendations(similarity_matrix, for_vectorisation)

    # Now output to a file
    with open('recommendations.json', 'w') as f:
        json.dump(recommendations, f, indent=4)

    print("Recommendations written to recommendations.json")

    update_firestore(recommendations)


if __name__ == "__main__":
    main()
