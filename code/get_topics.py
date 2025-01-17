#!/usr/bin/env python
# -*- coding: utf-8 -*-
# based on a script written by Chenhao Tan, modified by Dora Demszky, and later, Lucy Li
import functools
import json
import logging
from nltk import *
import itertools
import numpy as np
from collections import Counter, defaultdict
import io
import numpy as np
import re
import string
from scipy.stats import entropy

ROOT = '/mnt/data0/lucy/gpt3_bias/'
LOGS = ROOT + 'logs/' 
DATA = ROOT + 'data/'

stopwords = set(open(DATA + 'jockers_stopwords', 'r').read().lower().split(', '))
namewords = set(open(LOGS + 'prompt_char_names.txt', 'r').read().split())
stopwords = stopwords | namewords
punct_chars = list((set(string.punctuation) | {'»', '–', '—', '-',"­", '\xad', '-', '◾', '®', '©','✓','▲', '◄','▼','►', '~', '|', '“', '”', '…', "'", "`", '_', '•', '*', '■'} - {"'"}))
punct_chars.sort()
punctuation = ''.join(punct_chars)
replace = re.compile('[%s]' % re.escape(punctuation))
printable = set(string.printable)

logging.basicConfig(level=logging.INFO)

def find_bigrams(sentences, output_file, threshold=100, min_count=5):
    '''
    sentences - list of lines or sentences
    
    get bigrams following Mikolov et al. 2013, where min_count is discounting coeff   
    '''
    unigram_count = get_word_count(sentences, ngrams=1, words_func=get_ngram_list)
    total_words = float(sum(unigram_count.values()))
    bigram_count = get_word_count(sentences, ngrams=2, words_func=get_ngram_list)

    bigram_list = []
    for w in bigram_count:
        words = w.split()
        score = (bigram_count[w] - min_count) * total_words \
                / (unigram_count[words[0]] * unigram_count[words[1]])
        if score > threshold:
            bigram_list.append((score, w))
    bigram_list.sort(reverse=True)
    with open(output_file, "w") as fout:
        for score, w in bigram_list:
            fout.write("%s\n" % json.dumps({"word": w, "score": score}))


def get_ngram_list(input_words, ngrams=1, bigram_dict=None):
    words = [w.lower() for w in input_words.split()]
    result = []
    for start in range(len(words) - ngrams + 1):
        tmp_words = words[start:start + ngrams]
        w = " ".join(tmp_words)
        result.append(w)
    return result


def get_mixed_tokens(input_words, ngrams=1, bigram_dict=None):
    words = [w.lower() for w in input_words.split()]
    result, index = [], 0
    while index < len(words):
        w = words[index]
        # look forward
        if index < len(words) - 1:
            bigram = w + " " + words[index + 1]
            if bigram in bigram_dict:
                result.append(bigram)
                index += 2
                continue
        result.append(w)
        index += 1
    return result


def get_word_count(sentences, ngrams=1, bigram_dict=None, words_func=None):
    result = defaultdict(int)
    for sent in sentences:
        words = words_func(sent, ngrams=ngrams, bigram_dict=bigram_dict)
        for w in words:
            result[w] += 1
    return result


def load_bigrams(filename):
    bigram_dict = {}
    with open(filename) as fin:
        for line in fin:
            data = json.loads(line)
            bigram_dict[data["word"]] = data["score"]
    return bigram_dict


def get_word_dict(word_count, top=10000, filter_regex=None):
    if filter_regex:
        word_count = {w: word_count[w] for w in word_count
                      if all([re.match(filter_regex, sw) for sw in w.split()])}
    words = get_most_frequent(word_count, top=top)
    return {v[1]: i for i, v in enumerate(words)}


def get_most_frequent(word_cnt, top=10000):
    words = [(word_cnt[w], w) for w in word_cnt
             if re.match("\w+", w)]
    words.sort(reverse=True)
    min_threshold = words[min(top, len(words)) - 1][0]
    return [v for v in words if v[0] >= min_threshold]


def write_word_dict(vocab_dict, word_count, filename):
    with io.open(filename, mode="w", encoding="utf-8") as fout:
        ids = sorted(vocab_dict.values())
        reverse_dict = {i: w for (w, i) in vocab_dict.items()}
        for wid in ids:
            fout.write("%d\t%s\t%d\n" % (wid, reverse_dict[wid],
                word_count[reverse_dict[wid]]))

def convert_word_count_mallet(word_dict, sentences, output_file,
                              words_func=None):
    doc_id = 0
    with open(output_file, "w") as fout:
        for sent in sentences:
            doc_id += 1
            words = Counter(words_func(sent))
            words = [(word_dict[w], words[w])
                     for w in words if w in word_dict]
            words.sort()
            word_cnts = [" ".join([str(wid)] * cnt) for (wid, cnt) in words]
            fout.write("%s 0 %s\n" % (doc_id, " ".join(word_cnts)))

def get_mallet_input_from_words(sentences, data_dir, word_dict_path, data_input_path, bigram_file, vocab_size=10000):
    '''
    sentences - list of inputs (sentences or lines)
    data_dir - where to write the output 
    Writes input for mallet. 
    '''
    find_bigrams(sentences, bigram_file)
    bigram_dict = load_bigrams(bigram_file)
    word_cnts = get_word_count(sentences, bigram_dict=bigram_dict, words_func=get_mixed_tokens)
    vocab_dict = get_word_dict(word_cnts, top=vocab_size, filter_regex="\w\w+")
    write_word_dict(vocab_dict, word_cnts,
                          word_dict_path)
    convert_word_count_mallet(vocab_dict, sentences,
                              data_input_path,
                              words_func=functools.partial(
                                  get_mixed_tokens,
                                  bigram_dict=bigram_dict))

def read_word_dict(filename, vocab_size=-1):
    vocab_map = {}
    with io.open(filename, "r", encoding="utf-8") as fin:
        count = 0
        for line in fin:
            count += 1
            if vocab_size > 0 and count > vocab_size:
                break
            try:
                wid, word, _ = line.strip().split("\t")
                vocab_map[word] = int(wid)
            except:
                print(line)
    return vocab_map

def load_topic_words(vocab, input_file, top=10):
    """Get the top 10 words for each topic"""
    topic_map = {}
    with open(input_file) as fin:
        for line in fin:
            parts = line.strip().split()
            tid = int(parts[0])
            top_words = parts[2:2+top]
            topic_map[tid] = ",".join([vocab[int(w)] for w in top_words])
    return topic_map


def load_doc_topics(sentences, doc_topic_file, threshold):
    """Load topics in each document"""
    articles = []
    with open(doc_topic_file) as tfin:
        for _ in sentences:
            topic_line = tfin.readline()
            if not topic_line:
                break
            topics = topic_line.strip().split()[2:]
            topics = set([i for (i, v) in enumerate(topics)
                         if float(v) > threshold])
            articles.append(topics)
    return articles

def load_articles(sentences, topic_dir, threshold):
    vocab_file = "%s/data.word_id.dict" % topic_dir
    doc_topic_file = "%s/doc-topics.gz" % topic_dir
    topic_word_file = "%s/topic-words.gz" % topic_dir
    vocab = read_word_dict(vocab_file)
    # top 10 words per topic
    topic_map = load_topic_words(vocab, topic_word_file) 
    # topics in each doc
    articles = load_doc_topics(sentences, doc_topic_file, threshold=threshold) 
    return articles, vocab, topic_map

def clean_text(text): 
    text = text.strip().lower()
    replace = re.compile('[%s]' % re.escape(punctuation))
    # substitute all other punctuation with whitespace
    text = replace.sub(' ', text)
    # replace all whitespace with a single space
    text = re.sub(r'\s+', ' ', text)
    # make sure all chars are printable
    text = ''.join([c for c in text if c in printable])
    words = text.split()
    # remove stopwords
    words = [w for w in words if w not in stopwords]
    return ' '.join(words)

def train_lda_mallet():
    output_dir = LOGS + 'topics_0.9'
    mallet_dir = ROOT + 'mallet-2.0.8/bin'
    input_dir = LOGS + 'plaintext_stories_0.9/'
    orig_dir = LOGS + 'book_excerpts/'
    num_topics = 50
    
    all_text = []
    num_words = []
    story_ids = []
    for title in sorted(os.listdir(input_dir)): 
        with open(input_dir + title, 'r') as infile: 
            story_idx = 0
            dot_count = 0
            line_count = 0
            curr_story = '' # trying this
            for line in infile: 
                if line.strip() == '@': 
                    dot_count += 1
                else: 
                    dot_count = 0
                if dot_count == 20: 
                    story_idx += 1
                    num_words.append(len(curr_story.split()))
                    all_text.append(curr_story)
                    story_ids.append(title + str(story_idx))
                    curr_story = ''
                    line_count = 0
                elif line.strip() != '' and line.strip() != '@':
                    text = clean_text(line) 
                    curr_story += text + ' ' 
                    line_count += 1

    for title in sorted(os.listdir(orig_dir)): 
        with open(orig_dir + title, 'r') as infile: 
            story_idx = 0
            dot_count = 0
            curr_story = '' # trying this
            for line in infile: 
                if line.strip() == '@': 
                    dot_count += 1
                else: 
                    dot_count = 0
                if dot_count == 20: 
                    story_idx += 1
                    num_words.append(len(curr_story.split()))
                    all_text.append(curr_story)
                    story_ids.append('ORIG_' + title + str(story_idx))
                    curr_story = ''
                elif line.strip() != '' and line.strip() != '@':
                    text = clean_text(line) 
                    curr_story += text + ' ' 

    with open(output_dir + '/story_id_order', 'w') as outfile: 
        for story_i in story_ids: 
            outfile.write(story_i + '\n')
    assert len(story_ids) == len(all_text)
    print("Average number of tokens per story:", np.mean(num_words))
    
    # generate mallet topics
    logging.info("generating mallet inputs...")
    bigram_file = "%s/bigram_phrases.txt" % data_dir
    word_dict_path = "%s/data.word_id.dict" % data_dir
    data_input_path = "%s/data.input" % data_dir
    get_mallet_input_from_words(all_text, output_dir, word_dict_path, data_input_path, bigram_file)

    # run mallet to prepare topics inputs
    # users can also generate mallet-style topic inputs inputs
    logging.info("running mallet to get topics")
    if not os.path.exists(os.path.join(mallet_dir, 'mallet')):
        sys.exit("Error: Unable to find mallet at %s" % mallet_dir)
    os.system("./mallet.sh %s %s %d" % (mallet_dir,
                                        output_dir,
                                        num_topics))


    # load mallet outputs
    logging.info("loading outputs...")
    articles, vocab, topic_names = load_articles(all_text, output_dir, threshold=.1)
    save_topic_names = '%s/topic_names.json' % output_dir
    with open(save_topic_names, 'w') as f:
        f.write(json.dumps(topic_names))

    print(topic_names) # look at topics and top 10 words per topic 
    
def write_inference_input(): 
    output_dir = LOGS + 'topics_0.9'
    all_text = []
    
    for title in sorted(os.listdir(LOGS + 'original_prompts/')): 
        with open(LOGS + 'original_prompts/' + title, 'r') as infile:
            for line in infile: 
                contents = line.strip().split('\t')
                prompt = contents[2]
                if '-RRB-' in prompt or '-LRB-' in prompt: 
                    prompt = prompt.replace(' -RRB-', ')').replace('-LRB- ', '(')
                    prompt = prompt.replace('-RRB-', ')').replace('-LRB-', '(')
                prompt = clean_text(prompt)
                all_text.append(prompt)
    
    bigram_file = "%s/bigram_phrases.txt" % output_dir
    word_dict_path = "%s/data.word_id.dict" % output_dir
    data_input_path = "%s/infer_data.input" % output_dir
    vocab_dict = read_word_dict(word_dict_path)
    bigram_dict = load_bigrams(bigram_file)
    convert_word_count_mallet(vocab_dict, all_text,
                              data_input_path,
                              words_func=functools.partial(
                                  get_mixed_tokens,
                                  bigram_dict=bigram_dict))
    
def get_topic_prompts(): 
    '''
    Output: nested dictionaries of {title: {char_storyID: value}}
    '''
    num_gens = 5
    output_dir = LOGS + 'topics_0.9/'
    topicID1 = 35
    topicID2 = 33
    
    with open(output_dir + 'topic_names.json', 'r') as infile: 
        topic_names = json.load(infile)
    
    fem_topic_value = []
    masc_topic_value = []
    with open(output_dir + 'infered_docs', 'r') as infile: 
        for line in infile: 
            if line.startswith('#'): continue
            contents = line.split('\t')
            doc = int(contents[0])
            topics = [float(i) for i in contents[2:]]
            fem_topic_value.append(topics[topicID1])
            masc_topic_value.append(topics[topicID2])
    idx = 0
    topic_score_dict1 = defaultdict(Counter)
    topic_score_dict2 = defaultdict(Counter)
    for title in sorted(os.listdir(LOGS + 'original_prompts/')): 
        story_idx = 0
        with open(LOGS + 'original_prompts/' + title, 'r') as infile:
            for line in infile: 
                contents = line.strip().split('\t')
                char = contents[1]
                prompt = contents[2]
                if '-RRB-' in prompt or '-LRB-' in prompt: 
                    prompt = prompt.replace(' -RRB-', ')').replace('-LRB- ', '(')
                    prompt = prompt.replace('-RRB-', ')').replace('-LRB-', '(')
                for i in range(story_idx, story_idx + num_gens): 
                    char_ID = char + '_' + str(i)
                    if fem_topic_value[idx] > 0.15: 
                        print("-----------", prompt)
                    if masc_topic_value[idx] > 0.15: 
                        print("***********", prompt)
                    topic_score_dict1[title][char_ID] = fem_topic_value[idx]
                    topic_score_dict2[title][char_ID] = masc_topic_value[idx]
                story_idx += num_gens 
                idx += 1
                
    with open(output_dir + str(topicID1) + '_prompt_topic_scores.json', 'w') as outfile: 
        json.dump(topic_score_dict1, outfile)
    with open(output_dir + str(topicID2) + '_prompt_topic_scores.json', 'w') as outfile: 
        json.dump(topic_score_dict2, outfile)
        
def compare_topic_dist(): 
    '''
    Comparing the topic distribution between the prompt and story
    for generated books and book excerpts
    '''
    num_gens = 5
            
    gen_prompt_order = []
    orig_prompt_order = []
    for title in sorted(os.listdir(LOGS + 'original_prompts/')): 
        story_idx1 = 1
        story_idx2 = 1
        with open(LOGS + 'original_prompts/' + title, 'r') as infile:
            for line in infile: 
                for idx in range(story_idx1, story_idx1 + num_gens): 
                    gen_prompt_order.append(title + str(idx))
                orig_prompt_order.append(title + str(story_idx2))
                story_idx1 += num_gens
                story_idx2 += 1
                
    # get prompt topic distributions
    gen_prompt_topics = {} # { title + story_idx : [probabilities] }
    orig_prompt_topics = {}
    output_dir = LOGS + 'topics_0.9/'
    with open(output_dir + 'infered_docs', 'r') as infile: 
        story_idx1 = 0
        story_idx2 = 0
        for line in infile: 
            if line.startswith('#'): continue
            contents = line.split('\t')
            doc = int(contents[0])
            topics = [float(i) for i in contents[2:]]
            for idx in range(story_idx1, story_idx1 + num_gens): 
                gen_prompt_topics[gen_prompt_order[idx]] = topics
            orig_prompt_topics[orig_prompt_order[story_idx2]] = topics
            story_idx1 += num_gens
            story_idx2 += 1
    
    # get book excerpt and generated story topic distributions
    doc_topic_file = '%sdoc-topics.gz' % output_dir
    doc_topics = open(doc_topic_file).read().splitlines() # list of topics
    story_ids = open(output_dir + 'story_id_order').read().splitlines() # story IDs 
    story_topics = {}
    for i, doc in enumerate(doc_topics): 
        contents = doc.split('\t')
        topics = [float(i) for i in contents[2:]]
        story_title_id = story_ids[i]
        story_topics[story_title_id] = topics 
        
    assert (len(gen_prompt_topics) + len(orig_prompt_topics)) == len(story_topics)
    
    orig_kld_scores = []
    for story_title_id in orig_prompt_topics: 
        prob_dist1 = orig_prompt_topics[story_title_id]
        prob_dist2 = story_topics['ORIG_' + story_title_id]
        orig_kld_scores.append(entropy(prob_dist2, qk=prob_dist1))
    print(np.mean(orig_kld_scores), np.var(orig_kld_scores))
        
    gen_kld_scores = []
    for story_title_id in gen_prompt_topics: 
        prob_dist1 = gen_prompt_topics[story_title_id]
        prob_dist2 = story_topics[story_title_id]
        gen_kld_scores.append(entropy(prob_dist2, qk=prob_dist1))
    print(np.mean(gen_kld_scores), np.var(gen_kld_scores))
    
    np.save(LOGS + 'gen_kld_scores.npy', np.array(gen_kld_scores))
    np.save(LOGS + 'orig_kld_scores.npy', np.array(orig_kld_scores))
            
def main(): 
    #get_topic_prompts()
    #write_inference_input() 
    compare_topic_dist()

if __name__ == "__main__":
    main()

