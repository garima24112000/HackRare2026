#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
Script Name:    hpo_functions.py
Created:        2025-02-25
Version:        1.0

Description:
    (Maybe?) helpful functions for reading in an HPO ontology file and performing
    a VERY BASIC comparisons between sets of phenotype terms

Usage:
    python hpo_functions.py

Dependencies:
    - Python 3.x
    - Required libraries: pronto, math
===============================================================================
"""

import pronto
import math


def load_ontology(path_to_obo):
    """
    :param path_to_obo: full path to the .obo file downloaded from HPO
    :return: a pronto Ontology object containing HPO IDs, terms, and relationships
    """

    return pronto.Ontology(path_to_obo)  # Ignore the UnicodeWarning!


def read_disease_annotations(hpo_disease_annotations):
    """
    :param hpo_disease_annotations: full path to the tab-delimited "phenotype.hpoa" file downloaded from HPO
    :return: dictionary from disease ID -> set of corresponding HPO terms AND dictionary from disease ID -> name
    """

    disease_to_hpo = {}
    disease_to_name = {}

    with open(hpo_disease_annotations, 'r') as anno_handle:
        header = None
        for anno_line in anno_handle:

            if anno_line.startswith('#'):
                continue

            if not header:
                header = anno_line.strip().split('\t')
                continue

            disease_id, disease_name, _, hpo_id = anno_line.split('\t')[0:4]

            if disease_id not in disease_to_hpo:  # create dictionary of disease -> set (HPO terms)
                disease_to_hpo[disease_id] = set()
                disease_to_name[disease_id] = disease_name
            disease_to_hpo[disease_id].add(hpo_id)

    print("Number of diseases with annotations = " + str(len(disease_to_hpo.keys())))
    print("Average number terms/disease = " + str(
        sum([len(v) for v in disease_to_hpo.values()]) / len(disease_to_hpo.keys())))

    return disease_to_hpo, disease_to_name


def hpo_term_probability(disease_to_hpo):
    """
    :param disease_to_hpo: dictionary from disease ID -> set of HPO terms (computed in function "read_disease_annotations")
    :return: dictionary from HPO ID -> probability (to be used in information content calculations)
    """

    hpo_disease_prob = {}
    total_annotated_diseases = len(disease_to_hpo.keys())

    for disease, hpo_set in disease_to_hpo.items():
        for hpo_id in hpo_set:
            hpo_disease_prob[hpo_id] = hpo_disease_prob.get(hpo_id, 0) + 1
    for hpo_id in hpo_disease_prob.keys():
        hpo_disease_prob[hpo_id] = hpo_disease_prob[hpo_id] / total_annotated_diseases

    return hpo_disease_prob


def IC_term(hpo_term, probabilities):
    """
    :param hpo_term: a specific HPO term (e.g., 'HP:0001631')
    :param probabilities: dictionary from HPO ID -> probability (computed in function "hpo_term_probability")
    :return: information content of the input HPO term
    """

    if hpo_term in probabilities:
        return -1 * math.log2(probabilities[hpo_term])
    else:
        return 0


def IC(term_set, probabilities):
    """
    :param term_set: set of HPO terms (e.g., {'HP:0000059', 'HP:0000164', 'HP:0000248', 'HP:0000252')
    :param probabilities: dictionary from HPO ID -> probability (computed in function "hpo_term_probability")
    :return: total (sum) information content of the set of input HPO terms
    """

    total_information_content = 0
    for hpo_id in term_set:
        total_information_content += IC_term(hpo_id, probabilities)

    return total_information_content


def get_ancestors_up_to_root(ontology, start_term, stop_term='HP:0000118'):
    """
    :param ontology: pronto Ontology object (computed in function "load_ontology")
    :param start_term: specific HPO term (e.g., 'HP:0000164')
    :param stop_term: root term, known to be 'HP:0000118' (phenotypic abnormality)
    :return: set of all parent terms up to the root term
    """

    ancestors = set()
    current_term = ontology[start_term]

    for parent in current_term.superclasses():
        if parent.id == current_term.id: # first item is always the term itself
            continue
        if parent.id == stop_term:
            break
        ancestors.add(parent.id)

    return ancestors


if __name__ == "__main__":

    # -----------------------------------------------------------------------------------------------
    # Explore the ontology structure
    path_to_obo = '~/Downloads/hp.obo'
    path_to_disease_anno = '~/Downloads/phenotype.hpoa'

    pheno_ontology = load_ontology(path_to_obo)

    # Example patient with the following standardized phenotype terms
    patient = {'HP:0000059', 'HP:0000164', 'HP:0000248', 'HP:0000252', 'HP:0000276', 'HP:0000308',
               'HP:0000411', 'HP:0000448', 'HP:0000574', 'HP:0000717', 'HP:0001344', 'HP:0001537',
               'HP:0001631', 'HP:0002058', 'HP:0002126', 'HP:0002212', 'HP:0002269', 'HP:0002342',
               'HP:0002558', 'HP:0004749', 'HP:0006337', 'HP:0012169'}

    # Find the names of the patient's phenotype terms
    for term_id in sorted(list(patient)):
        term_name = pheno_ontology[term_id].name
        print(term_id + '\t' + term_name)

    # Find the Level 1 categories of these phenotype terms
    root_term = "HP:0000118"

    level_one_categories = set()  # fill this set with all Level 1 categories

    for child_term in pheno_ontology[root_term].subclasses(distance=1):
        if child_term.id != root_term:
            level_one_categories.add(child_term.id)

    # now, iterate through the patient HPO terms to determine which level one categories are in their ancestral sets:
    category_counts = {}  # fill this dictionary with level one category -> # patient phenotype terms in this category

    for term_id in patient:
        for parent in pheno_ontology[term_id].superclasses():
            if parent.id in level_one_categories:
                category_counts[parent.id] = category_counts.get(parent.id, 0) + 1

    for v, k in sorted([(v, k) for k, v in category_counts.items()], reverse=True):
        print(k + '\t' + pheno_ontology[k].name + ' (' + str(v) + ' terms)')

    # -----------------------------------------------------------------------------------------------
    # Compute similarity between patient and each disease

    # get the patient's ancestral set of phenotype terms:
    patient_ancestral_set = set()
    for hpo_term in patient:
        patient_ancestral_set.update(get_ancestors_up_to_root(pheno_ontology, hpo_term))

    # (1) get each disease's ancestral set of phenotype terms
    # (2) compute the overlap between the disease's and patient's ancestral terms
    # (3) find the information content of the overlapping terms as a BASIC similarity measure

    disease_to_hpo, disease_to_name = read_disease_annotations(path_to_disease_anno)
    hpo_disease_prob = hpo_term_probability(disease_to_hpo)

    disease_patient_sim_scores = []  # tuples of disease similarity score, disease name
    for disease, hpo_set in disease_to_hpo.items():

        disease_ancestral_set = set()

        for hpo_term in hpo_set:
            disease_ancestral_set.update(get_ancestors_up_to_root(pheno_ontology, hpo_term))
        disease_patient_sim_scores.append((IC(patient_ancestral_set.intersection(disease_ancestral_set),
                                              hpo_disease_prob), disease))

    # print out the top 10 diseases:
    top_diseases = sorted(disease_patient_sim_scores, reverse=True)[:10]
    for disease_sim_score, disease_id in top_diseases:
        print(disease_to_name[disease_id] + '\t' + str(disease_sim_score))

    # NOTE: There are far better ways to compute similarities between sets of HPO terms!
    # e.g., Phrank is FAST and performs well: https://www.nature.com/articles/s41436-018-0072-y
