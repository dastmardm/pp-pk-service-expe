
import os, json
import re, ast
import requests
from dotenv import dotenv_values

from .provider_clients import get_openai_client
from .prompts import pp_base_safety_translation, pp_base_pk_translation
from .termite import Termite7ResponseHandler

# Loading environment variables from the .env file
env_path = os.path.join(os.path.dirname(__file__), "configurations", ".env")
config = dotenv_values(os.path.abspath(env_path))

class Pharmapendium_API:
    def __init__(self):
        self.last_termite_entity_details = []
        try:
            self.termite_response_handler = Termite7ResponseHandler(
                url=config["TERMITE_HOME"],
                auth_url=config["TERMITE_AUTH_URL"],
                client_name=config["TERMITE_CLIENT_NAME"],
                client_secret=config["TERMITE_CLIENT_SECRET"],
                ontologies=["PP_DRUG","PP_AE","PP_TOX","PP_SPECIES","PP_ROUTE","PP_INDICATION","PP_TARGET","PP_PK","PP_AGE"],
            )
        except Exception as e:
            print(f"Error initializing TERMiteResponseHandler: {e}")
            self.termite_response_handler = None
    
    @staticmethod
    def fetch_all_items(payload_req, url, headers):
        all_items = []
        first_row = 0
        count_total = None
        
        while True:
            payload_req['limitation'] = {'firstRow': first_row}

            resp = requests.post(url, headers=headers, json=payload_req)
            if not resp.ok:
                print(f"PP API request failed: {resp.status_code} {resp.text}")
                break
            data = resp.json().get('data', {})
            
            items = data.get('items', [])
            if not items:
                break
            all_items.extend(items)
            
            if count_total is None:
                count_total = data.get('countTotal', None)
                if count_total is None:
                    break
            count_limited = data.get('countLimited', len(items))
            first_row += count_limited
            if first_row >= count_total:
                break
        return resp.json(), all_items

    @staticmethod
    def extract_payload_req(llm_response: str) -> dict:
        # Try fenced JSON first
        match = re.search(r"```json\s*(.*?)\s*```", llm_response, re.DOTALL | re.IGNORECASE)
        if match:
            raw = match.group(1).strip()
            try:
                return json.loads(raw)
            except json.JSONDecodeError as e:
                return {
                    "_error": "json_parse_failed",
                    "_where": "fenced_block",
                    "_exception": str(e),
                    "_raw_snippet": raw[:400],
                }

        # Fall back: first {...} object via brace matching
        start = llm_response.find("{")
        if start == -1:
            return {"_error": "no_json_found", "_raw_snippet": llm_response[:400]}

        end = Pharmapendium_API._find_matching_brace(llm_response, start)
        if end is None:
            return {"_error": "brace_match_failed", "_raw_snippet": llm_response[start:start+400]}

        raw = llm_response[start:end].strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            return {
                "_error": "json_parse_failed",
                "_where": "brace_extract",
                "_exception": str(e),
                "_raw_snippet": raw[:400],
            }


    @staticmethod
    def _find_matching_brace(text: str, start: int) -> int:
        """
        Find the closing brace matching an opening brace at position start.
        Handles escaped characters and strings properly.
        
        Args:
            text: The text to search
            start: Index of the opening brace
            
        Returns:
            Index of the closing brace, or None if not found
        """
        depth = 0
        in_string = False
        escape = False

        for i in range(start, len(text)):
            ch = text[i]
            
            if escape:
                escape = False
                continue
            
            if ch == "\\":
                escape = True
                continue
                
            if ch == '"':
                in_string = not in_string
                continue

            if not in_string:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return i + 1

        return None

    def solr_json_translation(self, query: str, service: str = 'safety', prompt_override=None):
        """
        Translates a user query into a SOLR-compatible JSON query using TERMite annotations.
        """
        annotated_query = query
        try:
            # Get annotations for the query using TERMite:
            self.termite_response_handler.refresh_request_builder()
            print('Annotating the user query using TERMite... ', self.termite_response_handler.ontologies)
            annotated_query, self.last_termite_entity_details = (
                self.termite_response_handler.get_mark_up_with_entity_details(query)
            )
            annotated_query = (
            annotated_query
            .replace("PP_DRUG", "DRUG")
            .replace("PP_AE", "ADVERSE_EVENT")
            .replace("PP_TOX", "TOXICITY_PARAMETER")
            .replace("PP_SPECIES", "SPECIES")
            .replace("PP_ROUTE", "ROUTE")
            .replace("PP_INDICATION", "INDICATION")
            .replace("PP_TARGET", "TARGET")
            .replace("PP_PK", "PARAMETER")
            .replace("PP_AGE", "AGE")
            )
            print('Annotated query: ', annotated_query)
            print(
                'TERMite entity details: ',
                json.dumps(
                    self.last_termite_entity_details,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
        except Exception as e:
            self.last_termite_entity_details = []
            print(f"Error during TERMite annotation: {e}")

        if service == 'safety':
            prompt_template = prompt_override or pp_base_safety_translation
            prompt = prompt_template.replace("{{it}}", query).replace("{{it_annotated}}", annotated_query)
        elif service == 'pk':
            prompt_template = prompt_override or pp_base_pk_translation
            prompt = prompt_template.replace("{{it}}", query).replace("{{it_annotated}}", annotated_query)
        else:
            print('Error! Unknown PP service requested.')
            return {}
        llm = get_openai_client(model_name=config["TOOL_MODEL"])
        response = llm.invoke(prompt).content
        
        # Debugging: Print the raw LLM response to understand its structure
        #print("RAW LLM RESPONSE PP API:\n", response) 

        json_query = self.extract_payload_req(response)
        return json_query, annotated_query
    
    def get_solr_response(self, payload_req, service, fetch_all=False):
        if service == 'safety':
            url = "https://api-dev.ppnp.cm-elsevier.com/v1/safety/search/advanced"
        elif service == 'pk':
            url = "https://api-dev.ppnp.cm-elsevier.com/v1/pk/search/advanced"
        elif service == 'moa':
            url = "https://api-dev.ppnp.cm-elsevier.com/v1/moa/search"
        else:
            print('Error! Unknown PP service requested.')
        
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json"
        }
        
        if fetch_all:
            response, all_items = self.fetch_all_items(payload_req, url, headers)
            return response, all_items
        else:
            response = requests.post(url, headers=headers, json=payload_req)
            if response.ok:
                response_json = response.json()
                items = response_json.get('data', {}).get('items', [])
                return response_json, items
            else:
                print(f"PP API request failed: {response.status_code} {response.text}")
                return {
                        "error": "pp_api_request_failed",
                        "status_code": response.status_code,
                        "body": response.text,
                        "service": service,
                    }, []
    
    def retrieve_structured_data(self, query, service, fetch_all=False, prompt_override=None):
        json_query, annotated_query = self.solr_json_translation(query, service, prompt_override)
        print("SOLR query: ", json_query)

        # Hard stop on translation failure
        if not json_query or json_query.get("_error"):
            return {
                "error": "structured_query_translation_failed",
                "details": json_query,
            }, [], json_query, annotated_query

        structured_response, all_items = self.get_solr_response(json_query, service, fetch_all)

        if structured_response and structured_response.get("data", {}).get("items") is not None:
            return structured_response, all_items, json_query, annotated_query
        
        else:
            return {
                "error": "no_relevant_records_found",
                "details": structured_response if structured_response else None,
            }, [], json_query, annotated_query
