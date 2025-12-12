from typing import Any, List, Optional 
from dataclasses import dataclass

@dataclass
class PipelineDef:
    """
    Represents a complete machine-learning or anomaly-detection pipeline
    ready to be executed in production.

    This class bundles together:
    - A unique pipeline identifier.
    - The trained model object.
    - The preprocessing / feature-transformation steps applied before inference.
    - Optional training data used for explanations, retraining, or analysis.
    """

    def __init__(
        self,
        id: str,
        model: Any,
        steps: List[tuple],
        X_train: Optional[Any] = None
    ):

        """
        Initializes a new PipelineDef instance.

        Args:
            id (str): Unique identifier for this pipeline.
            model (Any): Trained predictive model.
            steps (List[Tuple]): Preprocessing / transformation steps.
            X_train (Any, optional): Optional training dataset.
        """

        self.id = id
        self.model = model
        self.steps = steps 
        self.X_train = X_train