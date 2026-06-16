from __future__ import annotations

from typing import Dict, List, Tuple, Optional, Any, Union
from scibite_toolkit import termite7
from scibite_toolkit import termite
import html
import json
import logging
import pandas as pd


class Termite7ResponseHandler:
    """
    Wraps SciBite Termite calls and returns:
      - termited_text: normalized text containing tags like `{!~NAME~|~TYPE~|~ID~!}`
      - links_by_hit_id: dict[hitID] -> list[(label, url)]
    """

    def __init__(
        self,
        url: str,
        auth_url: str = None,
        client_name: str = None,
        client_secret: str = None,
        ontologies: Optional[List[str]] = None,
        centree_url: Optional[str] = None,
    ):
        if ontologies is None:
            ontologies = ["DRUG", "INDICATION", "HGNCGENE","SPECIES"]

        self.ontologies = ontologies
        self.centree_url = centree_url

        self.termite_instance = termite7.Termite7RequestBuilder()

        self.termite_instance.set_token_url(auth_url)
        self.termite_instance.set_url(url)
        self.termite_instance.set_oauth2(client_name, client_secret)

        self.termite_url = url
        self.termite_auth_url = auth_url
        self.termite_client_name = client_name
        self.termite_client_secret = client_secret

    def refresh_request_builder(self):
        trb = termite7.Termite7RequestBuilder()
        trb.set_token_url(self.termite_auth_url)
        trb.set_url(self.termite_url)
        trb.set_oauth2(self.termite_client_name, self.termite_client_secret)
        self.termite_instance = trb

    def get_mark_up(
        self,
        text: str,
        vocabs: Optional[List[str]] = None,
    ) -> str:
        """
        Returns:
        termited_text: str
        (optionally later: links_by_hit_id)

        Args:
        text: Input text
        vocabs: Optional list of vocab IDs to prioritize/filter in markup.
                If None, defaults to self.ontologies.
        """
        termited_text, _ = self.get_mark_up_with_entity_details(text, vocabs)
        return termited_text

    def get_mark_up_with_entity_details(
        self,
        text: str,
        vocabs: Optional[List[str]] = None,
    ) -> tuple[str, List[Dict[str, Any]]]:
        """
        Return TERMite markup plus compact entity diagnostics for UI/debugging.
        """
        vocabs = vocabs or self.ontologies

        termite_json = self.termite_instance.annotate_text(
            text=text,
            vocabulary=vocabs,
        )

        # substitution_dict = {ont: "{!~NAME~|~TYPE~|~ID~!}" for ont in vocabs}
        substitution_dict = {ont: "{! ~NAME~ | ~TYPE~ !}" for ont in vocabs}

        termited_text = self.text_markup(
            text=text,
            annotations=termite_json,
            replacementDict=substitution_dict,
            vocabs=vocabs,
        )

        return termited_text, self.extract_entity_details(
            termite_json,
            text=text,
            vocabs=vocabs,
        )

    @staticmethod
    def _clean_entity_id(vocab_id: str, entity_id: Any) -> Any:
        if isinstance(entity_id, str) and "$" in entity_id:
            left, right = entity_id.split("$", 1)
            if left == vocab_id:
                return right
        return entity_id

    @classmethod
    def extract_entity_details(
        cls,
        annotation_output: Union[str, Dict[str, Any], List[Dict[str, Any]], None],
        text: Optional[str] = None,
        vocabs: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract the TERMite entities that were matched, including IDs and spans.
        """
        if annotation_output is None:
            return []
        if isinstance(annotation_output, str):
            ann = json.loads(annotation_output)
        else:
            ann = annotation_output
        if isinstance(ann, list):
            ann = {"data": ann, "included": []}
        if not isinstance(ann, dict):
            return []

        allowed_vocabs = set(vocabs) if vocabs else None
        details: List[Dict[str, Any]] = []
        for entity_group in ann.get("included", []) or []:
            if not isinstance(entity_group, dict):
                continue
            entities = entity_group.get("entities", [])
            if not isinstance(entities, list):
                continue
            for entity in entities:
                if not isinstance(entity, dict):
                    continue
                vocab_id = entity.get("vocabularyId")
                if allowed_vocabs is not None and vocab_id not in allowed_vocabs:
                    continue

                occurrences = []
                surfaces: List[str] = []
                for occ in entity.get("occurrences", []) or []:
                    if not isinstance(occ, dict):
                        continue
                    start = occ.get("startChar")
                    end = occ.get("endChar")
                    surface = occ.get("text")
                    if (
                        not surface
                        and isinstance(text, str)
                        and isinstance(start, int)
                        and isinstance(end, int)
                        and 0 <= start < end <= len(text)
                    ):
                        surface = text[start:end]
                    if surface and surface not in surfaces:
                        surfaces.append(surface)
                    occurrences.append(
                        {
                            "text": surface or "",
                            "startChar": start,
                            "endChar": end,
                            "startByte": occ.get("startByte"),
                            "endByte": occ.get("endByte"),
                        }
                    )

                entity_id = entity.get("id")
                details.append(
                    {
                        "surface": "; ".join(surfaces),
                        "name": entity.get("name", ""),
                        "vocabularyId": vocab_id,
                        "id": entity_id,
                        "conceptId": cls._clean_entity_id(str(vocab_id or ""), entity_id),
                        "publicUri": entity.get("publicUri", ""),
                        "occurrenceCount": len(occurrences),
                        "occurrences": occurrences,
                    }
                )
        return details

    def process_annotation_output(self, annotation_output, logger=None):
        """
        Processes the annotation output and returns a pandas DataFrame with the entity id, name, publicUri, and number of occurrences.

        Parameters
        ----------
        annotation_output : dict
            The output from the TERMite annotation API.
        logger : logging.Logger, optional
            Logger to use instead of the root logger.

        Returns
        -------
        pd.DataFrame
            A DataFrame with columns:
            ["Entity ID", "Name", "Public URI", "Occurrences", "FirstStartChar", "FirstStartByte"].
        """
        log = logger or logging.getLogger(__name__)

        if not isinstance(annotation_output, dict):
            log.error(
                "Invalid input: expected dict, got %s", type(annotation_output).__name__
            )
            raise ValueError("annotation_output must be a dictionary")

        included_entities = annotation_output.get("included", [])
        if not included_entities:
            log.warning("No 'included' entities found in annotation output")
            return pd.DataFrame(
                columns=[
                    "Entity ID",
                    "Name",
                    "Public URI",
                    "Occurrences",
                    "FirstStartChar",
                    "FirstStartByte",
                ]
            )

        data = []

        for entity_group in included_entities:
            entities = entity_group.get("entities", [])
            for entity in entities:
                occurrences = entity.get("occurrences", [])
                first_occ = occurrences[0] if occurrences else {}

                data.append(
                    {
                        "Entity ID": entity.get("id", "N/A"),
                        "Name": entity.get("name", "N/A"),
                        "Public URI": entity.get("publicUri", "N/A"),
                        "Occurrences": len(occurrences),
                        "FirstStartChar": first_occ.get("startChar"),
                        "FirstStartByte": first_occ.get("startByte"),
                    }
                )

        df = pd.DataFrame(
            data,
        )

        log.info("Processed %d entities into DataFrame", len(df))

        return df

    def text_markup(
        self,
        text: Optional[str] = None,
        annotations: Union[str, Dict[str, Any], List[Dict[str, Any]]] = None,
        vocabs: Optional[List[str]] = None,
        normalisation: str = "id",
        wrap: bool = False,
        wrapChars: Tuple[str, str] = ("{!", "!}"),
        substitute: bool = True,
        replacementDict: Optional[Dict[str, str]] = None,
        include_json: bool = False,
    ):
        """
        Inject inline entities into text using Termite7 JSON.
        """

        if annotations is None:
            raise ValueError("annotations must be provided (termite7 json).")

        validTypes = {"id", "type", "name", "typeplusname", "typeplusid", "text"}
        if normalisation not in validTypes:
            raise ValueError(
                "Invalid normalisation. Valid options: "
                "'id', 'type', 'name', 'typeplusname', 'typeplusid', 'text'."
            )

        if len(wrapChars) != 2 or not all(isinstance(w, str) for w in wrapChars):
            raise ValueError(
                "wrapChars must be a tuple of length 2 containing strings."
            )

        # Parse input JSON
        if isinstance(annotations, str):
            ann = json.loads(annotations)
        else:
            ann = annotations

        if isinstance(ann, list):
            ann = {"data": ann, "included": []}

        data_items = ann.get("data", []) if isinstance(ann, dict) else []
        included = ann.get("included", []) if isinstance(ann, dict) else []

        # Gather included entities
        included_entities: List[Dict[str, Any]] = []
        for inc in included:
            if isinstance(inc, dict) and isinstance(inc.get("entities"), list):
                included_entities.extend(inc["entities"])

        # Build vocabulary priority map
        hierarchy: Dict[str, int] = {}
        if vocabs:
            for i, v in enumerate(vocabs):
                hierarchy[v] = i

        prefix, postfix = wrapChars if wrap else ("", "")

        def _clean_id(vocab_id: str, entity_id: str) -> str:
            if isinstance(entity_id, str) and "$" in entity_id:
                left, right = entity_id.split("$", 1)
                if left == vocab_id:
                    return right
            return entity_id

        def _priority(vocab_id: str) -> int:
            # Lower = higher priority
            if vocabs:
                return hierarchy.get(vocab_id, len(vocabs) + 10)
            return 0

        def _build_subtext(hit: Dict[str, Any]) -> str:
            etype = hit["entityType"]
            eid_clean = hit["entityID_clean"]
            ename = hit["entityName"]
            etext = hit["entityText"]

            if replacementDict and etype in replacementDict:
                tpl = replacementDict[etype]
                out = (
                    tpl.replace("~TYPE~", etype)
                    .replace("~ID~", eid_clean)
                    .replace("~NAME~", ename or "")
                    .replace("~TEXT~", etext or "")
                )
            else:
                if normalisation == "text":
                    out = etext
                elif normalisation == "id":
                    out = f"{etype}_{eid_clean}"
                elif normalisation == "type":
                    out = etype
                elif normalisation == "name":
                    out = ename
                elif normalisation == "typeplusname":
                    out = f"{etype} {ename}"
                elif normalisation == "typeplusid":
                    out = f"{etype} {etype}_{eid_clean}"
                else:
                    raise RuntimeError("Unhandled normalisation option.")

            if not substitute:
                out = f"{out} {etext}"

            return out

        def _dedupe_hits(candidate_hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            seen = set()
            deduped = []
            for hit in candidate_hits:
                key = (
                    hit["start"],
                    hit["end"],
                    hit["entityType"],
                    hit["entityID_clean"],
                    hit["entityName"],
                )
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(hit)
            return deduped

        def _build_multi_subtext(candidate_hits: List[Dict[str, Any]]) -> str:
            sorted_hits = sorted(
                _dedupe_hits(candidate_hits),
                key=lambda h: (
                    h["start"],
                    -(h["end"] - h["start"]),
                    h["priority"],
                    h["entityName"].lower(),
                    str(h["entityID_clean"]),
                ),
            )
            payload = ",".join(
                f"{{{hit['entityName']}|{hit['entityType']}|{hit['entityID_clean']}}}"
                for hit in sorted_hits
            )
            return f"{{![{payload}]!}}"

        results: Dict[int, Dict[str, str]] = {}

        for doc_idx, item in enumerate(data_items):
            if not isinstance(item, dict):
                results[doc_idx] = {"termited_text": ""}
                continue

            doc_text = text if text is not None else (item.get("input") or "")
            if not isinstance(doc_text, str):
                doc_text = ""

            if vocabs:
                allowed_vocabs = set(vocabs)
            else:
                vlist = item.get("vocabularies")
                allowed_vocabs = set(vlist) if isinstance(vlist, list) else None

            # Collect hits from included entities
            hits: List[Dict[str, Any]] = []
            for ent in included_entities:
                if not isinstance(ent, dict):
                    continue

                vocab_id = ent.get("vocabularyId")
                if not isinstance(vocab_id, str) or not vocab_id:
                    continue

                if allowed_vocabs is not None and vocab_id not in allowed_vocabs:
                    continue

                ent_id = ent.get("id", "")
                ent_name = ent.get("name", "") or ""
                occs = ent.get("occurrences") or []
                if not isinstance(occs, list):
                    continue

                for occ in occs:
                    if not isinstance(occ, dict):
                        continue

                    start = occ.get("startChar")
                    end = occ.get("endChar")
                    if not isinstance(start, int) or not isinstance(end, int):
                        continue
                    if start < 0 or end > len(doc_text) or end <= start:
                        continue

                    surface = doc_text[start:end]
                    hits.append(
                        {
                            "start": start,
                            "end": end,
                            "entityType": vocab_id,
                            "entityID_raw": ent_id,
                            "entityID_clean": _clean_id(vocab_id, ent_id),
                            "entityName": ent_name,
                            "entityText": surface,
                            "priority": _priority(vocab_id),
                        }
                    )

            if not hits:
                results[doc_idx] = {"termited_text": doc_text}
                continue

            # Stable sort (by start, then longer first, then priority)
            hits.sort(
                key=lambda h: (h["start"], -(h["end"] - h["start"]), h["priority"])
            )

            # Preserve overlapping hits by grouping each overlapping span cluster
            # into one inline multi-candidate annotation. This avoids nested markup
            # while keeping every TERMite candidate visible to the prompt/UI.
            span_groups: List[Dict[str, Any]] = []
            for h in hits:
                if not span_groups or h["start"] >= span_groups[-1]["end"]:
                    span_groups.append(
                        {
                            "start": h["start"],
                            "end": h["end"],
                            "hits": [h],
                        }
                    )
                    continue

                current = span_groups[-1]
                current["end"] = max(current["end"], h["end"])
                current["hits"].append(h)

            # Apply replacements from end to start
            out_text = doc_text
            for group in reversed(span_groups):
                group_hits = group["hits"]
                if len(_dedupe_hits(group_hits)) == 1:
                    subtext = _build_subtext(group_hits[0])
                else:
                    subtext = _build_multi_subtext(group_hits)
                out_text = (
                    out_text[: group["start"]]
                    + prefix
                    + subtext
                    + postfix
                    + out_text[group["end"] :]
                )

            results[doc_idx] = {"termited_text": out_text}

        if len(results) == 1:
            single = results[0]["termited_text"]
            return (single, ann) if include_json else single

        return (results, ann) if include_json else results

    def get_v7synonym_groups_json(self, input_text) -> str:
        """
        Process input text through Termite and return grouped synonyms as JSON.

        Args:
            input_text (str): The text to process for entity recognition

        Returns:
            str: JSON string with synonym groups mapping to unique entity names
        """
        # Process text through Termite
        data = self.process_annotation_output(input_text)

        # Select relevant columns
        data = data[["Name", "FirstStartChar"]]
        # Convert FirstStartChar to string for grouping (since lists are unhashable)
        data["FirstStartChar"] = data["FirstStartChar"].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else str(x)
        )
        # Group by FirstStartChar and create unique names list
        grouped_data = data.groupby("FirstStartChar")
        result = {}
        for synonym_list, group in grouped_data:
            # Get unique names for this synonym group (remove duplicates)
            unique_names = list(group["Name"].unique())
            result[synonym_list] = unique_names

        # Convert to JSON and return

        return json.dumps(result, indent=2)


class TermiteResponseHandler:
    """
    Wraps SciBite Termite calls and returns:
      - termited_text: normalized text containing tags like `{!~NAME~|~TYPE~|~ID~!}`
      - links_by_hit_id: dict[hitID] -> list[(label, url)]
    """

    def __init__(
        self,
        url: str,
        saas_login_url: Optional[str] = None,
        ontologies: Optional[List[str]] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        output_format: str = "json",
        centree_url: Optional[str] = None,
        subsume: bool = True,
        fuzzy: bool = False,
    ):
        if ontologies is None:
            ontologies = ["DRUG", "INDICATION", "GENE"]

        self.ontologies = ontologies
        self.centree_url = centree_url

        self.termite_instance = termite.TermiteRequestBuilder()
        self.termite_instance.set_url(url)
        if saas_login_url is not None:
            self.termite_instance.set_saas_login_url(saas_login_url)
        self.termite_instance.set_entities(",".join(ontologies))
        self.termite_instance.set_subsume(subsume)
        self.termite_instance.set_fuzzy(fuzzy)
        if username is not None and password is not None:
            self.termite_instance.set_auth_saas(username, password)
        self.termite_instance.set_output_format(output_format)

    # -------------------- public helpers --------------------

    def get_termite_dataframe(self, text: str):
        self._set_text(text)
        termite_response = self.termite_instance.execute()
        return termite.get_termite_dataframe(termite_response)

    def get_mark_up(self, text: str) -> tuple[str, Dict[str, List[Tuple[str, str]]]]:
        """
        Returns:
          termited_text: str
          links_by_hit_id: dict[hitID] -> list[(label, url)]
        """
        self._set_text(text)
        self.termite_instance.set_output_format("doc.jsonx")
        termite_json = self.termite_instance.execute()

        # Make the normalized text with placeholders
        substitution_dict = {ont: "{!~NAME~|~TYPE~|~ID~!}" for ont in self.ontologies}
        normalized = termite.markup(termite_json, replacementDict=substitution_dict)
        termited_text = normalized[0]["termited_text"]

        # Build links per hitID using the full JSON (type/name/id/mappings)
        # links_by_hit_id = self._build_links_index(termite_json)

        return termited_text

    # Link generation tech

    def _build_links_index(self, termite_json) -> Dict[str, List[Tuple[str, str]]]:
        """
        Build dict: { hitID -> [(label, url), ...] }
        Uses hit fields and mapping xrefs where present.
        """
        links_index: Dict[str, List[Tuple[str, str]]] = {}
        mappings_by_hit = self._build_mappings_dict(termite_json)

        # termite_json[0]['termiteTags'] typically has the entities
        for hit in termite_json[0].get("termiteTags", []):
            hit_id = hit.get("hitID", "").strip()
            if not hit_id:
                continue

            name = (hit.get("pref") or hit.get("term") or "").strip() or "Entity"
            etype = (hit.get("type") or hit.get("entityType") or "").strip()
            # Build list of links for this hit
            links: List[Tuple[str, str]] = []

            # Always try CENtree first (works even without mappings)
            cen = self._build_centree_url(hit_id, etype, name)
            if cen:
                links.append(("CENtree", cen))

            # Type-specific resources (mostly for DRUG) based on mappings/xrefs
            mx = mappings_by_hit.get(
                hit_id, {}
            )  # mapping dict for this hit (scheme->id)
            drug_like = etype.upper() == "DRUG"

            if drug_like:
                self._maybe_add(
                    links, "ChEMBL", self._build_chembl_url(hit_id, etype, name, mx)
                )
                self._maybe_add(
                    links, "PDB", self._build_pdb_url(hit_id, etype, name, mx)
                )
                self._maybe_add(
                    links, "ChEBI", self._build_chebi_url(hit_id, etype, name, mx)
                )
                self._maybe_add(
                    links, "DrugBank", self._build_drugbank_url(hit_id, etype, name, mx)
                )
                self._maybe_add(
                    links, "PharmGKB", self._build_pharmgkb_url(hit_id, etype, name, mx)
                )
                self._maybe_add(
                    links, "IUPHAR", self._build_iuphar_url(hit_id, etype, name, mx)
                )
                self._maybe_add(
                    links,
                    "ChemSpider",
                    self._build_chemspider_url(hit_id, etype, name, mx),
                )
                self._maybe_add(
                    links, "PubChem", self._build_pubchem_url(hit_id, etype, name, mx)
                )
                self._maybe_add(
                    links,
                    "SureChEMBL",
                    self._build_surechembl_url(hit_id, etype, name, mx),
                )
                self._maybe_add(
                    links, "HMDB", self._build_hmdb_url(hit_id, etype, name, mx)
                )

            links_index[hit_id] = links

        return links_index

    @staticmethod
    def _maybe_add(lst: List[Tuple[str, str]], label: str, url: Optional[str]) -> None:
        if url:
            lst.append((label, url))

    def _set_text(self, text: str):
        self.termite_instance.set_text(text)

    def _build_mappings_dict(self, termite_json) -> dict:
        """
        Create dict of shape {hitID: {id_scheme_name: mapped_id}} for xrefs.
        Only records mappings whose relation is 'xref'.
        """

        def parse_mapping_collection(mappings):
            d = {}
            for mapping in mappings:
                # mapping is like "SCHEME|ID|REL"
                parts = mapping.split("|")
                if len(parts) >= 3 and parts[2].lower() == "xref":
                    d[parts[0].lower()] = parts[1]
            return d

        md = {}
        for hit in termite_json[0].get("termiteTags", []):
            md[hit["hitID"]] = parse_mapping_collection(hit.get("mappings", []))
        return md

    def _build_centree_url(
        self, entity_id: str, entity_type: str, entity_name: str
    ) -> Optional[str]:
        """
        CENtree URLs vary by type; fallback to a text search if we don't have a base URL.
        """
        base = (self.centree_url or "").strip()
        if not base:
            # Fallback: send to a generic web search by name
            return f"https://www.google.com/search?q={html.escape(entity_name)}"

        if entity_type == "EMTREE":
            return f"{base}/client/ontologies/emtree_rmc/classes?primaryID=https://data.elsevier.com/lifescience/emtree/{entity_id}"
        elif entity_type == "INDICATION":
            return f"{base}/client/ontologies/indication/classes?primaryID=http://id.nlm.nih.gov/mesh/{entity_id}"
        else:
            # Generic search
            return f"{base}/client/search?query={html.escape(entity_name)}"

    @staticmethod
    def _build_chembl_url(
        entity_id: str, entity_type: str, entity_name: str, mx: dict
    ) -> Optional[str]:
        if entity_type.strip().upper() != "DRUG":
            return None
        # If we already have a CHEMBL id mapping, prefer it
        chembl = None
        # Some feeds may store "chembl" or "chemblid"; try both
        for key in ("chembl", "chemblid"):
            if key in mx:
                chembl = mx[key]
                break
        if chembl:
            return f"https://www.ebi.ac.uk/chembl/compound_report_card/{chembl}/"
        # Otherwise search by name
        return f"https://www.ebi.ac.uk/chembl/search?q={html.escape(entity_name)}"

    @staticmethod
    def _build_pdb_url(
        entity_id: str, entity_type: str, entity_name: str, mx: dict
    ) -> Optional[str]:
        if entity_type.strip().upper() != "DRUG":
            return None
        pdb = mx.get("pdb")
        return f"https://www.rcsb.org/ligand/{html.escape(pdb)}" if pdb else None

    @staticmethod
    def _build_chebi_url(
        entity_id: str, entity_type: str, entity_name: str, mx: dict
    ) -> Optional[str]:
        if entity_type.strip().upper() != "DRUG":
            return None
        chebi = mx.get("chebi")
        if not chebi:
            return None
        # Ensure it looks like a numeric id (Termite often has just the number)
        chebi = str(chebi).replace("CHEBI:", "")
        return f"https://www.ebi.ac.uk/chebi/searchId.do?chebiId=CHEBI:{html.escape(chebi)}"

    @staticmethod
    def _build_drugbank_url(
        entity_id: str, entity_type: str, entity_name: str, mx: dict
    ) -> Optional[str]:
        if entity_type.strip().upper() != "DRUG":
            return None
        db = mx.get("drugbank")
        return f"https://go.drugbank.com/drugs/{html.escape(db)}" if db else None

    @staticmethod
    def _build_pharmgkb_url(
        entity_id: str, entity_type: str, entity_name: str, mx: dict
    ) -> Optional[str]:
        if entity_type.strip().upper() != "DRUG":
            return None
        pg = mx.get("pharmgkb")
        return f"https://www.pharmgkb.org/chemical/{html.escape(pg)}" if pg else None

    @staticmethod
    def _build_iuphar_url(
        entity_id: str, entity_type: str, entity_name: str, mx: dict
    ) -> Optional[str]:
        if entity_type.strip().upper() != "DRUG":
            return None
        iuphar = mx.get("iuphar")
        return (
            f"https://www.guidetopharmacology.org/GRAC/LigandDisplayForward?ligandId={html.escape(iuphar)}"
            if iuphar
            else None
        )

    @staticmethod
    def _build_chemspider_url(
        entity_id: str, entity_type: str, entity_name: str, mx: dict
    ) -> Optional[str]:
        if entity_type.strip().upper() != "DRUG":
            return None
        cs = mx.get("chemspider")
        return (
            f"https://www.chemspider.com/Chemical-Structure.{html.escape(cs)}.html"
            if cs
            else None
        )

    @staticmethod
    def _build_pubchem_url(
        entity_id: str, entity_type: str, entity_name: str, mx: dict
    ) -> Optional[str]:
        if entity_type.strip().upper() != "DRUG":
            return None
        pc = mx.get("pubchem")
        return (
            f"https://pubchem.ncbi.nlm.nih.gov/compound/{html.escape(pc)}"
            if pc
            else None
        )

    @staticmethod
    def _build_surechembl_url(
        entity_id: str, entity_type: str, entity_name: str, mx: dict
    ) -> Optional[str]:
        if entity_type.strip().upper() != "DRUG":
            return None
        sc = mx.get("surechembl")
        return f"https://www.surechembl.org/chemical/{html.escape(sc)}" if sc else None

    @staticmethod
    def _build_hmdb_url(
        entity_id: str, entity_type: str, entity_name: str, mx: dict
    ) -> Optional[str]:
        if entity_type.strip().upper() != "DRUG":
            return None
        hmdb = mx.get("hmdb")
        return f"https://hmdb.ca/metabolites/{html.escape(hmdb)}" if hmdb else None

    # -------------------- KG helpers --------------------

    def get_synonym_groups_json(self, input_text) -> str:
        """
        Process input text through Termite and return grouped synonyms as JSON.

        Args:
            input_text (str): The text to process for entity recognition

        Returns:
            str: JSON string with synonym groups mapping to unique entity names
        """
        # Process text through Termite
        data = self.get_termite_dataframe(input_text)

        # Select relevant columns
        data = data[["name", "realSynList"]]

        # Convert realSynList to string for grouping (since lists are unhashable)
        data["realSynList"] = data["realSynList"].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else str(x)
        )

        # Group by realSynList and create unique names list
        grouped_data = data.groupby("realSynList")
        result = {}
        for synonym_list, group in grouped_data:
            # Get unique names for this synonym group (remove duplicates)
            unique_names = list(group["name"].unique())
            result[synonym_list] = unique_names

        # Convert to JSON and return
        return json.dumps(result, indent=2)
