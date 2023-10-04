import pytest
import unittest
from typing import Set
from flaky import flaky

import numpy as np

from deepchem.utils.batch_utils import create_input_array

try:
    import torch
    from deepchem.models.torch_models.seqtoseq import SeqToSeq, SeqToSeqModel
    has_torch = True
except:
    has_torch = False

# Dataset of SMILES strings for testing SeqToSeq models.
train_smiles = [
    'Cc1cccc(N2CCN(C(=O)C34CC5CC(CC(C5)C3)C4)CC2)c1C',
    'Cn1ccnc1SCC(=O)Nc1ccc(Oc2ccccc2)cc1',
    'COc1cc2c(cc1NC(=O)CN1C(=O)NC3(CCc4ccccc43)C1=O)oc1ccccc12',
    'O=C1/C(=C/NC2CCS(=O)(=O)C2)c2ccccc2C(=O)N1c1ccccc1',
    'NC(=O)NC(Cc1ccccc1)C(=O)O', 'CCn1c(CSc2nccn2C)nc2cc(C(=O)O)ccc21',
    'CCc1cccc2c1NC(=O)C21C2C(=O)N(Cc3ccccc3)C(=O)C2C2CCCN21',
    'COc1ccc(C2C(C(=O)NCc3ccccc3)=C(C)N=C3N=CNN32)cc1OC',
    'CCCc1cc(=O)nc(SCC(=O)N(CC(C)C)C2CCS(=O)(=O)C2)[nH]1',
    'CCn1cnc2c1c(=O)n(CC(=O)Nc1cc(C)on1)c(=O)n2Cc1ccccc1'
]

tokens: Set[str] = set()
for s in train_smiles:
    tokens = tokens.union(set(c for c in s))
token_list = sorted(list(tokens))

batch_size = len(train_smiles)

max_length = max(len(s) for s in train_smiles)


def generate_sequences(sequence_length, num_sequences):
    for i in range(num_sequences):
        seq = "".join([
            str(np.random.randint(10))
            for x in range(np.random.randint(1, sequence_length + 1))
        ])
        yield (seq, seq)


@pytest.mark.torch
def test_seqtoseq():
    """Test the SeqToSeq Class."""
    global token_list
    token_list = token_list + [" "]
    input_dict = dict((x, i) for i, x in enumerate(token_list))
    n_tokens = len(token_list)
    embedding_dimension = 16
    model = SeqToSeq(n_tokens, n_tokens, max_length, batch_size,
                     embedding_dimension)
    inputs = create_input_array(train_smiles, max_length, False, batch_size,
                                input_dict, " ")
    output, embeddings = model([torch.tensor(inputs), torch.tensor([1])])
    assert output.shape == (batch_size, max_length, n_tokens)
    assert embeddings.shape == (1, batch_size, embedding_dimension)


@pytest.mark.torch
def test_seqtoseq_model():
    """Test learning to reproduce short sequences of integers."""
    sequence_length = 8
    tokens = list(str(x) for x in range(10))
    model = SeqToSeqModel(tokens,
                          tokens,
                          sequence_length,
                          embedding_dimension=512,
                          learning_rate=0.01,
                          dropout=0.1)
    # Train the model on random sequences. We aren't training long enough to
    # really make it reliable, but I want to keep this test fast, and it should
    # still be able to reproduce a reasonable fraction of input sequences.
    model.fit_sequences(generate_sequences(sequence_length, 25000))
    # Test it out.
    tests = [seq for seq, target in generate_sequences(sequence_length, 100)]
    pred1 = model.predict_from_sequences(tests, beam_width=1)
    pred4 = model.predict_from_sequences(tests, beam_width=4)
    embeddings = model.predict_embedding(tests)
    pred1e = model.predict_from_embedding(embeddings, beam_width=1)
    pred4e = model.predict_from_embedding(embeddings, beam_width=4)
    count1 = 0
    count4 = 0
    for i in range(len(tests)):
        if "".join(pred1[i]) == tests[i]:
            count1 += 1
        if "".join(pred4[i]) == tests[i]:
            count4 += 1
        assert pred1[i] == pred1e[i]
        assert pred4[i] == pred4e[i]
    # Check that it got at least a quarter of them correct.
    assert count1 >= 25
    assert count4 >= 25


@flaky(3, 2)
@pytest.mark.torch
def test_variational():
    """Test using a SeqToSeq model as a variational autoenconder."""
    sequence_length = 10
    tokens = list(str(x) for x in range(10))
    model = SeqToSeqModel(tokens,
                          tokens,
                          sequence_length,
                          embedding_dimension=128,
                          learning_rate=0.01,
                          variational=True)
    # Actually training a VAE takes far too long for a unit test.  Just run a
    # few steps of training to make sure nothing crashes, then check that the
    # results are at least internally consistent.
    model.fit_sequences(generate_sequences(sequence_length, 100))
    for sequence, target in generate_sequences(sequence_length, 10):
        pred1 = model.predict_from_sequences([sequence], beam_width=1)
        embedding = model.predict_embedding([sequence])
        assert pred1 == model.predict_from_embedding(embedding, beam_width=1)
