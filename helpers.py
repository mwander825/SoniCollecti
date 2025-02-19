from typing import Union
import pandas as pd
import re

ws_match = re.compile(r"\s{2,}")


# clean & standardize string
# can remove all Unicode characters BE CAREFUL!!!
def css(s: Union[str, pd.Series], clobber_utf: bool=False) -> Union[str, pd.Series]:
    if not clobber_utf:
        if isinstance(s, str):
            return ws_match.sub(" ", s).lower().strip()
        elif isinstance(s, pd.Series):
            return s.apply(lambda st: ws_match.sub(" ", st)).str.lower().str.strip()
    else:
        if isinstance(s, str):
            return ws_match.sub(" ", s.encode("ASCII", errors="ignore").decode("ASCII", errors="ignore").lower().strip())
        elif isinstance(s, pd.Series):
            return s.apply(lambda st: ws_match.sub(" ", st.encode("ASCII", errors="ignore").decode("ASCII", errors="ignore"))).str.lower().str.strip()
