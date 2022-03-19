import os
import pickle
import numpy as np
import pandas as pd
import streamlit as st
from bson import ObjectId
from textblob import TextBlob
from pymongo import MongoClient
from sklearn.feature_extraction.text import CountVectorizer #, TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from sklearn import metrics
from sklearn.metrics import confusion_matrix
# from sklearn.metrics.pairwise import cosine_similarity
# import requests
# import matplotlib.pyplot as plt

# https://scikit-learn.org/stable/modules/naive_bayes.html


# Get the current working directory
cwd = os.getcwd()

st.set_page_config(
    page_title="Ex-stream-ly Cool App",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="expanded"
)


def load_classifier():
    f = open(cwd+'/model_files/nb_classifier', 'rb')
    clf = pickle.load(f)
    f.close()
    return clf


def load_vect():
    # define a function that accepts text and returns a list of lemons (verb version)
    f = open(cwd+'/model_files/vect', 'rb')
    vect = pickle.load(f)
    f.close()
    return vect


def word_tokenize_lemma_verb(text):
    words = TextBlob(text).words
    return [word.lemmatize(pos = "v") for word in words]


vect = CountVectorizer(
                  stop_words="english", 
                  analyzer=word_tokenize_lemma_verb,
                  max_features=10000
            )


# def get_feature_importance(item, VECT, FeatImportance):
#     payload_features = pd.DataFrame(item.toarray(), columns=VECT.get_feature_names(), index=['values']).T
#     payload_features = payload_features[payload_features.values>0].reset_index()    
#     payload_features.columns = ['tokens', 'values'] 
#     good_features = FeatImportance.merge(payload_features['tokens'], on="tokens", how='inner').sort_values('featureImportance', ascending=False)
#     # Positive Features will be on top (hence ".head()"). Negative Features (".tail()")
#     st.write('Here are the outstanding features: ')
#     # st.write(good_features['index'].values)
#     return good_features



st.write(
'''
# Data Engineering (March 2022)
### *Yelp Star Rating Classifier - Yelp Dataset*
Maybe you've heard about a restaurant that you've been wanting to try. You've heard comments from friends and family, but don't quite trust their opinion! 
Given a sample of text, we try to predict if this will be a good or bad review. 
Sample the out of the box model that is already pre-trained, or learn how to build a text classifier model on your own!

[Additional info on the dataset](https://yelp.com/dataset/)

'''
)


# Connect to MongoDB
client = MongoClient()
# client.list_database_names()
db = client.yelpdb
collection = db.reviews



n_good_bad_samples = 50000

@st.cache()
def load_data(NUM_REVIEWS_EACH):
    df_rw_good = pd.DataFrame(list(collection.find({"stars":{"$gte":4}}, {"text": 1, 'stars':1}).limit(NUM_REVIEWS_EACH)))
    df_rw_bad = pd.DataFrame(list(collection.find({"stars":{"$lte":3}}, {"text": 1, 'stars':1}).limit(NUM_REVIEWS_EACH)))
    df_rw = pd.concat([df_rw_bad, df_rw_good], axis=0)
    del df_rw_bad
    del df_rw_good
    df_rw = df_rw.astype(str)

    def good_bad_review(x):
        """
        Reviews with star ratings 4 and above are considered "Good Reviews",
        and all other reviews are considered "Bad Reviews". This function will
        create a target variable in this binary classification approach
        """
        if x >= 4:
            return 1
        else:
            return 0



    df_rw['stars'] = df_rw['stars'].astype(float)
    df_rw['target'] = df_rw['stars'].apply(good_bad_review)
    # define X and y
    X = df_rw.text
    y = df_rw.target

    X_train, X_test, y_train, y_test = train_test_split(X, y, random_state=1)


    return df_rw, X_train, X_test, y_train, y_test, X, y

df_rw, X_train, X_test, y_train, y_test, X, y = load_data(n_good_bad_samples)




use_example_model = st.checkbox(
    "Use example model", True, help="Use pre-built example model to demo the app"
)


# If CSV is not uploaded and checkbox is filled, use values from the example file
# and pass them down to the next if block
if use_example_model:

    # Load pre-trained model files:
    clf = load_classifier()
    vect = load_vect()

    # plot learning curve
    # https://scikit-learn.org/stable/auto_examples/model_selection/plot_learning_curve.html
    col1, col2 = st.columns((1,1))

    col1.write("Examples of Bad Reviews: ")
    col1.write(df_rw[df_rw.target == 0]['text'].sample(n = 1).values[0])
    col2.write("Examples of Good Reviews: ")
    col2.write(df_rw[df_rw.target == 1]['text'].sample(n = 1).values[0])

    st.write(
    '''
    ## Predict if this is a Good or Bad review:
    '''
    )

    ###### CREATE TEXT INPUT FIELD ######
    # st.text_area("label", height=10)
    text_input = st.text_input("What have you heard about this place?:")
    st.write(text_input)
    payload_transformed = vect.transform([text_input])

    output = clf.predict(payload_transformed)[0]
    st.write("Probability:")
    st.write(pd.DataFrame(clf.predict_proba(payload_transformed), columns = ['prob_Bad', 'prob_Good']))


    if output == 1:
        output_str = "Good Review"
        st.write("This is a `{}`!".format(output_str))
    else:
        output_str = "Bad Review"
        st.write("This is a `{}`.. 🧐".format(output_str))



    if text_input:
        # Do you Agree with the review?
        # Collect Text Input
        client = MongoClient()
        db_feedback = client.yelpdb_feedback
        collection_feedback = db_feedback.reviews

        mydict = { "text": text_input, "target": output.astype(str)}

        x = collection_feedback.insert_one(mydict)
        x_id = x.inserted_id

        # GATHER FEEDBACK. Update document if the "target" is incorrect per user feedback!
        st.write("Do you think the prediction is correct? If not, please provide feedback: ")
        # FEEDBACK = (0, 1) dropdown bar (0 for "Bad Review", 1 for "Good Review")
        feedback = st.selectbox('Pick one', ['Bad Review', 'Good Review'])
        
        if feedback == "Bad Review":
            doc = collection_feedback.find_one_and_update(
            {"text" : text_input, "_id" : ObjectId(x_id)},
            {"$set":
                {"target": 0}
            },upsert=True
            )
        else:
            doc = collection_feedback.find_one_and_update(
            {"text" : text_input, "_id" : ObjectId(x_id)},
            {"$set":
                {"target": 1}
            },upsert=True
            )

        X_train_dtm = vect.fit_transform(X_train)
        featureImportance = pd.DataFrame(data = np.transpose((clf.fit(X_train_dtm, y_train).coef_).astype("float32")), columns = ['featureImportance'], 
                 index=vect.get_feature_names()).sort_values('featureImportance').reset_index()
        featureImportance.columns = ['tokens', 'featureImportance']


        if output_str == "Bad Review":
            # st.dataframe(featureImportance.head())
            # st.dataframe(featureImportance.tail())
            st.write(payload_transformed)
            st.write(payload_transformed.toarray())

            payload_features = pd.DataFrame(vect.transform([text_input]).toarray(), columns=vect.get_feature_names(), index=['values']).T
            payload_features = payload_features[payload_features.values>0].reset_index()    
            payload_features.columns = ['tokens', 'values'] 
            st.dataframe(payload_features)
            good_features = featureImportance.merge(payload_features['tokens'], on="tokens", how='inner').sort_values('featureImportance', ascending=False)
            # st.write(get_feature_importance(payload_transformed, vect, featureImportance).tail(100).values)
        else:
            print ("hihi")
            # st.write(get_feature_importance(payload_transformed, vect, featureImportance).head(100).values)



    # # -- Allow dataframe download. We want to include the 
    # download = {'Time':bp_cropped.times, 'Strain':bp_cropped.value}
    # df = pd.DataFrame(download)
    # csv = df.to_csv(index=False)
    # b64 = base64.b64encode(csv.encode()).decode()  # some strings <-> bytes conversions necessary here
    # fn =  detector + '-STRAIN' + '-' + str(int(cropstart)) + '-' + str(int(cropend-cropstart)) + '.csv'
    # href = f'<a href="data:file/csv;base64,{b64}" download="{fn}">Download Data as CSV File</a>'
    # st.markdown(href, unsafe_allow_html=True)




    # st.write(
    # '''
    # ### How to adjust model parameters to get even smarter...



    # 2nd LEVEL ADD FEEDBACK LOOP.. 
    # This was a miss. how to re-learn (what was wrong about this?)

    # "i love the everything but the kitchen sink pizza"..


    # Create an auto-update ID for each unique row to append
    # check in MongoDB

    # User imput of columns
    # - read if you already have a row for this, if not.. then add in a simple "update feedback" 

    # - unique text comment vs. text id..

    # - Feature Importance (NB)??? What does it look like for the Text Input?
    # https://blog.ineuron.ai/Feature-Importance-in-Naive-Bayes-Classifiers-5qob5d5sFW#:~:text=The%20naive%20bayes%20classifers%20don,class%20with%20the%20highest%20probability.

    # '''
    # )






else:

    # # Sidebar items:
    st.sidebar.markdown("# Controls")

    pick_model = st.sidebar.selectbox(
    "Pick a Classifier Model: ",
    ("MultinomialNB", "Logistic Regression"))   


    def add_parameter(clf_name):

        params = {}
        if pick_model == "MultinomialNB":
            max_features = st.sidebar.slider("max_features", min_value=1, max_value=10000, value=10000)
            params["max_features"] = max_features
        elif pick_model == "Logistic Regression":
            max_features = st.sidebar.slider("max_features", min_value=1, max_value=10000, value=10000)
            params["max_features"] = max_features
    
        return params

    df_rw, X_train, X_test, y_train, y_test, X, y = load_data(n_good_bad_samples)

    params = add_parameter(pick_model)

    bigram = st.sidebar.checkbox(
        "Use Bigrams", True, help="Enable ngram feature: (2,2)"
        )
    if bigram:
        params['ngram_range'] = (2,2)
    else:
        params['ngram_range'] = (1,1)

    all_stars = df_rw.stars.unique().tolist()
    stars = st.sidebar.multiselect(
        "Stars", options=all_stars, default=all_stars
    )

    vect = CountVectorizer(
                  stop_words="english", 
                  # analyzer=word_tokenize_lemma_verb,
                  max_features=params['max_features'],
                  ngram_range=params['ngram_range']
            )


    def build_model(model):
        X_train_dtm = vect.fit_transform(X_train)
        X_test_dtm = vect.transform(X_test)
        clf = model.fit(X_train_dtm, y_train)
        st.write("Selected Model: `{}`".format(pick_model))
        y_pred_class = model.predict(X_test_dtm)
        st.write("Dataset shape: `{}`".format(df_rw.shape))
        st.write("Testing Score: ", model.score(X_test_dtm, y_test))
        st.dataframe(confusion_matrix(y_test, y_pred_class))
        # Create a button for exporting out pickle file!
        # with open(cwd+'/model_files/custom_classifier', 'wb') as picklefile:
        #     pickle.dump(clf, picklefile)
        st.write(
        '''
        ## Predict if this is a Good or Bad review:
        '''
        )
        text_input = st.text_input("What have you heard about this place?:")
        st.write(text_input)
        a = vect.transform([text_input])

        output = clf.predict(a)[0]
        st.write("Probability:")
        # Return probability estimates for the test vector X.
        st.write(pd.DataFrame(clf.predict_proba(a), columns = ['prob_Bad', 'prob_Good']))
        
        # output_dict = {"Good Review": 1, "Bad Review": 0}

        if output == 1:
            output_str = "Good Review"
            st.write("This is a `{}`!".format(output_str))
        else:
            output_str = "Bad Review"
            st.write("This is a `{}`.. 🧐".format(output_str))

        featureImportance = pd.DataFrame(data = np.transpose((clf.fit(X_train_dtm, y_train).coef_).astype("float32")), columns = ['featureImportance'], 
                 index=vect.get_feature_names()).sort_values('featureImportance').reset_index()


        if output_str == "Bad Review":

            st.write(get_feature_importance(a, vect, featureImportance).tail(10).values)
        else:

            st.write(get_feature_importance(a, vect, featureImportance).head(10).values)




    
    if pick_model == "MultinomialNB":
        nb = MultinomialNB()
            # Build custom NB model:
        build_nb = build_model(nb)
        
    
    elif pick_model == "Logistic Regression":
        lr = LogisticRegression()
        build_lr = build_model(lr)
        # st.write(vect.get_feature_names()[-10:])





        # CONNECT TO STARS in SIDEBAR
        # plot_df = _df[_df.lang.isin(langs)]
        # plot_df["stars"] = plot_df.stars.divide(1000).round(1)

        # chart = (
        #     alt.Chart(
        #         plot_df,
        #         title="Static site generators popularity",
        #     )
        #     .mark_bar()
        #     .encode(
        #         x=alt.X("stars", title="'000 stars on Github"),
        #         y=alt.Y(
        #             "name",
        #             sort=alt.EncodingSortField(field="stars", order="descending"),
        #             title="",
        #         ),
        #         color=alt.Color(
        #             "lang",
        #             legend=alt.Legend(title="Language"),
        #             scale=alt.Scale(scheme="category10"),
        #         ),
        #         tooltip=["name", "stars", "lang"],
        #     )
        # )


        # st.altair_chart(chart, use_container_width=True)




        # with open(cwd+'/model_files/custom_classifier', 'wb') as picklefile:
        #     pickle.dump(clf, picklefile)




#Get the index values of the 3
# st.write("Selected business is {}, and the categories are {}".format(company_dict[add_selectbox], data.iloc[add_selectbox]['categories']))

# dist_column = df_dist[add_selectbox]

# # st.write(data.iloc[add_selectbox]['categories'])

# closest_index = dist_column.nlargest(5).index[1:].tolist()

# st.write(
# '''
# ## 
# Suggested businesses based on selection:
# ''')
# for i in closest_index:
#         st.write(i)
#         st.write((data.iloc[i]['name'], ": ", data.iloc[i]['categories']))
#         st.write('Cosine Similarity Score:', cosine_similarity(dist[add_selectbox].reshape(1,-1), dist[i].reshape(1,-1))[0][0])
#         st.write()



## PART 4 - Graphing and Buttons
#
# st.write(
# '''
# ### Graphing and Buttons
# Let's graph some of our data with matplotlib. We can also add buttons to add interactivity to our app.
# '''
# )

# fig, ax = plt.subplots()

# ax.hist(data['PRICE'])
# ax.set_title('Distribution of House Prices in $100,000s')

# show_graph = st.checkbox('Show Graph', value=True)

# if show_graph:
#     st.pyplot(fig)


# ## PART 5 - Mapping and Filtering Data
# #
# st.write(
# '''
# ## Mapping and Filtering Data
# We can also use Streamlit's built in mapping functionality.
# Furthermore, we can use a slider to filter for houses within a particular price range.
# '''
# )

# price_input = st.slider('House Price Filter', int(data['PRICE'].min()), int(data['PRICE'].max()), 500000 )

# price_filter = data['PRICE'] < price_input
# st.map(data.loc[price_filter, ['lat', 'lon']])


# # PART 6 - Linear Regression Model

# st.write(
# '''
# ## Train a Linear Regression Model
# Now let's create a model to predict a house's price from its square footage and number of bedrooms.
# '''
# ) 


# from sklearn.linear_model import LinearRegression
# from sklearn.model_selection import train_test_split

# clean_data = data.dropna(subset=['PRICE', 'SQUARE FEET', 'BEDS'])

# X = clean_data[['SQUARE FEET', 'BEDS']]
# y = clean_data['PRICE']

# X_train, X_test, y_train, y_test = train_test_split(X, y)

# ## Warning: Using the above code, the R^2 value will continue changing in the app. Remember this file is run upon every update! Set the random_state if you want consistent R^2 results.
# X_train, X_test, y_train, y_test = train_test_split(X, y, random_state=42)

# lr = LinearRegression()
# lr.fit(X_train, y_train)

# st.write(f'Test RÂ²: {lr.score(X_test, y_test):.3f}')


# # PART 7 - Predictions from User Input

# st.write(
# '''
# ## Model Predictions
# And finally, we can make predictions with our trained model from user input.
# '''
# )

# sqft = st.number_input('Square Footage of House', value=2000)
# beds = st.number_input('Number of Bedrooms', value=3)

# input_data = pd.DataFrame({'sqft': [sqft], 'beds': [beds]})
# pred = lr.predict(input_data)[0]

# st.write(
# f'Predicted Sales Price of House: ${int(pred):,}'
# )