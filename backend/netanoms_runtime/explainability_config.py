from typing import Any, Dict, Literal
from dataclasses import field

ExplainKind = Literal["none", "shap", "lime"]

class ExplainabilityConfig:
    """
    Holds the configuration required to enable model explainability within
    the live or offline anomaly-detection pipeline.

    This class specifies:
      - Which explainability method should be activated (e.g., SHAP or LIME).
      - The Python module where the explainer implementation is located.
      - The class name of the explainer to be dynamically imported.
      - Optional constructor arguments that should be passed to the explainer.

    It acts purely as a lightweight container used when constructing or
    executing a detection pipeline. No logic is performed inside this class;
    it simply provides structured, typed configuration data that other
    runtime components (such as the detection engine) can rely on.
    """

    def __init__(
        self,
        kind: ExplainKind = "none",
        module: str = "",
        explainer_class: str = "",
        explainer_kwargs: Dict[str, Any] = field(default_factory=dict)
    ):

        """
        Initializes a new ExplainabilityConfig instance.

        Args:
            kind (ExplainKind): The explainability method to use. Supported values are:
                - "none": No explainability enabled.
                - "shap": Use SHAP explainability techniques.
                - "lime": Use LIME explainability techniques.
            module (str):Python module where the explainer implementation resides.
            explainer_class (str): Name of the explainer class to instantiate.
            explainer_kwargs (Dict[str, Any], optional): Extra keyword arguments passed directly to the explainer constructor.
        """

        self.kind = kind
        self.module = module
        self.explainer_class = explainer_class 
        self.explainer_kwargs = explainer_kwargs or []