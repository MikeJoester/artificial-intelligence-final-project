import os
import pandas as pd
from langid.langid import LanguageIdentifier, model
import re
import string
import time
import torch
from torchtext.data.utils import get_tokenizer
from torchtext.vocab import build_vocab_from_iterator
from torchtext.data.functional import to_map_style_dataset
from torch.utils.data import DataLoader
from torch import nn

def load_data_from_path(folder_path):
    examples = []
    for label in os.listdir(folder_path):
        full_path = os.path.join (folder_path , label)
        for file_name in os.listdir (full_path):
            file_path = os.path . join (full_path, file_name)
            with open (file_path, "r", encoding ="utf-8") as f:
                lines = f.readlines()
            sentence = " ".join(lines)
            if label == "neg": label = 0
            if label == "pos": label = 1
            data = {
                'sentence': sentence ,
                'label': label
            }
            examples.append(data)
    return pd.DataFrame(examples)

folder_paths = {
    'train': './data/data_train/train',
    'valid': './data/data_train/test',
    'test': './data/data_test/test'
}
train_df = load_data_from_path(folder_paths ['train'])
valid_df = load_data_from_path(folder_paths ['valid'])
test_df = load_data_from_path(folder_paths ['test'])

def identify_vn (df):
    identifier = LanguageIdentifier.from_modelstring(model , norm_probs = True )
    not_vi_idx = set ()
    THRESHOLD = 0.9

    for idx, row in df.iterrows ():
        score = identifier.classify(row["sentence"])
        if score[0] != "vi" or (score [0] == "vi" and score [1] <= THRESHOLD):
            not_vi_idx.add(idx)
    vi_df = df [~df.index.isin(not_vi_idx)]
    not_vi_df = df[df.index.isin(not_vi_idx)]

    return vi_df , not_vi_df
train_df_vi , train_df_other = identify_vn ( train_df )

def preprocess_text(text):
    url_pattern = re.compile(r'https?://\s+\wwww\.\s+')
    text = url_pattern.sub(r" ", text)
    html_pattern = re.compile (r'<[^<>]+>')
    text = html_pattern.sub(" ", text)

    replace_chars = list(string.punctuation + string.digits)
    for char in replace_chars :
        text = text.replace(char, " ")

    emoji_pattern = re.compile ("["
        u"\ U0001F600 -\ U0001F64F " # emoticons
        u"\ U0001F300 -\ U0001F5FF " # symbols & pictographs
        u"\ U0001F680 -\ U0001F6FF " # transport & map symbols
        u"\ U0001F1E0 -\ U0001F1FF " # flags (iOS)
        u"\ U0001F1F2 -\ U0001F1F4 " # Macau flag
        u"\ U0001F1E6 -\ U0001F1FF " # flags
        u"\ U0001F600 -\ U0001F64F "
        u"\ U00002702 -\ U000027B0 "
        u"\ U000024C2 -\ U0001F251 "
        u"\ U0001f926 -\ U0001f937 "
        u"\ U0001F1F2 "
        u"\ U0001F1F4 "
        u"\ U0001F620 "
        u"\ u200d "
        u"\u2640 -\ u2642 "
    "]+", flags =re. UNICODE )
    text = emoji_pattern.sub(r" ", text)
    text = " ".join(text.split())

    return text.lower()

train_df_vi ['preprocess_sentence'] = [ preprocess_text ( row['sentence']) for index, row in train_df_vi.iterrows () ]
valid_df ['preprocess_sentence'] = [ preprocess_text ( row['sentence']) for index, row in valid_df.iterrows () ]
test_df ['preprocess_sentence'] = [ preprocess_text ( row['sentence']) for index, row in test_df.iterrows () ]


#word - based tokenizer
tokenizer = get_tokenizer("basic_english")

# create iter dataset
def yield_tokens (sentences, tokenizer):
    for sentence in sentences :
        yield tokenizer(sentence)
        
# build vocabulary
vocab_size = 10000
vocabulary = build_vocab_from_iterator(
    yield_tokens(train_df_vi['preprocess_sentence'], tokenizer),
    max_tokens = vocab_size,
    specials =["<unk>"]
)

vocabulary.set_default_index(vocabulary["<unk>"])

torch.save(vocabulary, "vocabulary.pth")

# convert iter into torchtext dataset
def prepare_dataset (df):
    for index, row in df.iterrows():
        sentence = row['preprocess_sentence']
        encoded_sentence = vocabulary(tokenizer(sentence))
        label = row['label']
        yield encoded_sentence, label

train_dataset = prepare_dataset(train_df_vi)
train_dataset = to_map_style_dataset(train_dataset)

valid_dataset = prepare_dataset(valid_df)
valid_dataset = to_map_style_dataset(valid_dataset)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

def collate_batch (batch):
    encoded_sentences, labels, offsets = [], [], [0]
    for encoded_sentence, label in batch :
        labels.append(label)
        encoded_sentence = torch.tensor ( encoded_sentence, dtype = torch.int64 )
        encoded_sentences.append (encoded_sentence)
        offsets.append ( encoded_sentence.size(0))

    labels = torch.tensor(labels , dtype = torch . int64 )
    offsets = torch.tensor( offsets [:-1]).cumsum(dim = 0)
    encoded_sentences = torch.cat(encoded_sentences)
    return encoded_sentences.to(device), offsets.to(device), labels.to(device)

batch_size = 128

train_dataloader = DataLoader (
    train_dataset,
    batch_size = batch_size,
    shuffle = True,
    collate_fn = collate_batch
)

valid_dataloader = DataLoader (
    valid_dataset,
    batch_size = batch_size,
    shuffle = False,
    collate_fn = collate_batch
)

class TextClassificationModel(nn.Module):
    def __init__(self , vocab_size , embed_dim , num_class):
        super ( TextClassificationModel , self ). __init__ ()
        self . embedding = nn. EmbeddingBag ( vocab_size , embed_dim , sparse = False )
        self .fc = nn. Linear ( embed_dim , num_class )
        self . init_weights ()

    def init_weights(self):
        initrange = 0.5
        self.embedding.weight.data.uniform_(- initrange, initrange )
        self.fc.weight.data.uniform_(- initrange, initrange )
        self.fc.bias.data.zero_()

    def forward (self, inputs, offsets):
        embedded = self . embedding (inputs , offsets )
        return self .fc( embedded )

num_class = len(set( train_df_vi ['label']))
vocab_size = len( vocabulary )
embed_dim = 256
model = TextClassificationModel( vocab_size, embed_dim, num_class ).to( device )

learning_rate = 5
criterion = torch.nn.CrossEntropyLoss ()
optimizer = torch.optim.SGD( model.parameters (), lr= learning_rate )

import torch
import time

def train(model, optimizer, criterion, train_dataloader, epoch=0, log_interval=25):
    model.train()
    total_acc, total_count = 0, 0
    losses = []
    start_time = time.time()

    for idx, (inputs, offsets, labels) in enumerate(train_dataloader):
        optimizer.zero_grad()
        predictions = model(inputs, offsets)

        # compute loss
        loss = criterion(predictions, labels)
        losses.append(loss.item())

        # backward
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 0.1)
        optimizer.step()
        total_acc += (predictions.argmax(1) == labels).sum().item()
        total_count += labels.size(0)

        if idx % log_interval == 0 and idx > 0:
            elapsed = time.time() - start_time
            print(
                "| epoch {:3d} | {:5d}/{:5d} batches \n | accuracy {:8.3f}".format(
                    epoch, idx, len(train_dataloader), total_acc / total_count
                )
            )
            total_acc, total_count = 0, 0
            start_time = time.time()

    epoch_acc = total_acc / total_count
    epoch_loss = sum(losses) / len(losses)

    # Save the model's state dictionary to a file
    torch.save(model.state_dict(), "trained_model.pth")

    return epoch_acc, epoch_loss

def evaluate (model , criterion , valid_dataloader ):
    model.eval ()
    total_acc , total_count = 0, 0
    losses = []

    with torch.no_grad():
        for idx , (inputs, offsets, labels ) in enumerate ( valid_dataloader ):
            predictions = model(inputs, offsets )
            loss = criterion(predictions, labels )
            losses . append(loss)
            total_acc += (predictions.argmax(1) == labels).sum().item()
            total_count += labels.size(0)

    epoch_acc = total_acc / total_count
    epoch_loss = sum(losses) / len (losses)
    return epoch_acc, epoch_loss

num_class = len(set( train_df_vi ['label']))
vocab_size = len( vocabulary )
embed_dim = 100
model = TextClassificationModel( vocab_size, embed_dim, num_class ).to(device)

learning_rate = 5
criterion = torch.nn.CrossEntropyLoss()
optimizer = torch.optim.SGD(model.parameters(), lr = learning_rate)

num_epochs = 6
for epoch in range(1, num_epochs +1):
    epoch_start_time = time.time()
    train_acc, train_loss = train(model, optimizer, criterion, train_dataloader, epoch)
    eval_acc, eval_loss = evaluate(model, criterion, valid_dataloader)
    print ("-" * 59)
    print (
        "| End of epoch {:3d} | Time : {:5.2f}s | Train Accuracy {:8.3f} | Train Loss {:8.3f} \n | Valid Accuracy {:8.3f} | Valid Loss {:8.3f} "
        .format(epoch, time.time() - epoch_start_time, train_acc , train_loss , eval_acc , eval_loss)
    )
    print ("-" * 59)
    # Save the model after each epoch
    
def predict ( text ):
    with torch.no_grad():
        encoded = torch.tensor(vocabulary(tokenizer(text)))
        output = model(encoded, torch.tensor([0]))
    return output.argmax(1).item()

predictions, labels = [], []
for index, row in test_df.iterrows ():
    sentence = row['preprocess_sentence']
    label = row['label']
    prediction = predict( sentence )
    predictions.append( prediction )
    labels.append( label )

sum (torch.tensor(predictions) == torch.tensor( labels ))/len(labels)