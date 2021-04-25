# Gender and Representation Bias in GPT-3 Generated Stories

This README is ordered according to sections in the paper, and each section describes corresponding scripts and materials involved in their production. 

Some TODOs for Lucy by end of May, once the semester is over: 

- comment every code file 
- delete deprecated code from unused experiments to avoid confusion
- describe each section below, and what parts of each script correspond to information in the paper 
- upload non-copyrighted intermediate files 

## Abstract
Using topic modeling and lexicon-based word similarity, we find that stories generated by GPT-3 exhibit many known gender stereotypes. Generated stories depict different topics and descriptions depending on GPT-3's perceived gender of the character in a prompt, with feminine characters more likely to be associated with family and appearance, and described as less powerful than masculine characters, even when associated with high power verbs in a prompt. Our study raises questions on how one can avoid unintended social biases when using large language models for storytelling.

## Requirements 

TBD by workshop date 

## Data

- query\_openai.py

We need to check that our data does not contain copyrighted book materials before release. 

## Text Processing 

- book\_nlp.sh
- check\_book\_bounds.py
- data\_organize.py
- dataset\_viz.ipynb
- get\_characters.py
- get\_entity\_info.py
- preprocessing.py
- segment\_original\_books.py

### Gender 

We do not recommend the use of these methods for inferring the actual gender of real people. 

- gender\_inference.py

### Matching

- prompt\_design.py

## Topics

- mallet.sh
- get\_topics.py
- character\_viz.ipynb

## Lexicons

- word\_embeddings.py
- character\_viz.ipynb
