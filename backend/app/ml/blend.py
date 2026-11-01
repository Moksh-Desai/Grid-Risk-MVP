import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin


# Lives in its own module so pickled models load the same way whether they
# were trained from the CLI (python -m app.ml.train) or by the server.
class BlendClassifier(ClassifierMixin, BaseEstimator):
    """Average of several fitted classifiers' probabilities."""

    def __init__(self, models=None):
        self.models = models
        self.classes_ = np.array([0, 1])

    def fit(self, X, y):  # already fitted; present for sklearn's scorer API
        return self

    def predict_proba(self, X):
        return np.mean([m.predict_proba(X) for m in self.models], axis=0)
