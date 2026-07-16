import traceback
from app.llm.provider import get_llm_provider
from app.schemas_engine import NLUIntent

try:
    provider = get_llm_provider()
    print('Provider:', type(provider))
    res = provider.generate_structured('Respond with metric=Revenue, intent=data', NLUIntent)
    print(res)
except Exception as e:
    traceback.print_exc()
