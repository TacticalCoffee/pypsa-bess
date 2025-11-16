# -*- coding: utf-8 -*-
"""
Created on Mon Nov  3 10:45:50 2025

@author: noego
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import datetime
from datetime import timedelta
from main import prep_network, plot_results, plot_energybalance, plot_evolstorage, plot_co2overtime, plot_scenarios, return_scenario

st.set_page_config(page_title="Simulation mix énergétique", layout="wide")

st.title("⚡ Simulation de réseau énergétique - France")

st.sidebar.header("Paramètres de simulation")

mois = {
    'janvier': 0,
    'février': 744,
    'mars': 1416,
    'avril': 2160,
    'mai': 2880,
    'juin': 3624,
    'juillet': 4344,
    'août': 5088,
    'septembre': 5832,
    'octobre': 6552,
    'novembre': 7296,
    'décembre': 8016
}

# --- Widgets utilisateur ---
time_horizon_in_hours = st.sidebar.slider("Durée de la simulation (jours)", 1, 31, 7, step=1)*24
widget_debut = st.sidebar.selectbox("Mois de départ",mois.keys())
date_debut = mois.get(widget_debut)

demand_multiplier = st.sidebar.slider("Facteur multiplicatif de la demande", 0.5, 2.0, 1.0, 0.1)
capa_data_year = st.sidebar.selectbox("Année de données de capacité", [2025, 2028, 2030, 2033])
charge_initiale_stockage = st.sidebar.slider("Taux initial de charge du stockage", 0.0, 1.0, 0.8, 0.1)

st.sidebar.markdown("---")
st.sidebar.subheader("Paramètres stockage")
p_bat = st.sidebar.number_input("Puissance batteries (MW)", 0, 2000, 470,100)
capa_bat = st.sidebar.number_input("Capacité batteries (MWh)", 0, 10000, 940,200)
p_hyd = st.sidebar.number_input("Puissance hydro (MW)", 0, 4000, 3800,500)
capa_hyd = st.sidebar.number_input("Capacité hydro (MWh)", 0, 200000, 100000,5000)


st.subheader("Aperçu du scénario choisi")

# with st.spinner(f"Chargement du scénario {capa_data_year}..."):
#     try:
#         plot_scenarios(capa_data_year)
#         st.pyplot(plt.gcf())
#     except Exception as e:
#         st.error(f"Impossible d'afficher l'aperçu du scénario {capa_data_year} : {e}")

scenario = return_scenario(capa_data_year)
st.subheader(f"Capacités installées - scénario {capa_data_year}")
st.dataframe(scenario.T)


# --- affichage de la période sélectionnée

st.subheader("Aperçu temporel")

year_hours = 8760
progress_start = date_debut / year_hours
progress_end = (date_debut + time_horizon_in_hours) / year_hours

st.progress(progress_start, text="Début de la période")
st.progress(progress_end, text="Fin de la période")

start_date = datetime.datetime(2012, 1, 1) + datetime.timedelta(hours=date_debut)
end_date = start_date + datetime.timedelta(hours=time_horizon_in_hours)
st.caption(f"Période : {start_date.strftime('%d %b %Y %H:%M')} → {end_date.strftime('%d %b %Y %H:%M')}")



# --- Lancement de la simulation ---
if st.button("🚀 Lancer la simulation"):
    with st.spinner("Préparation du réseau et lancement du solveur..."):
        network = prep_network(
            time_horizon_in_hours=int(time_horizon_in_hours),
            date_debut=int(date_debut),
            demand_multiplier=demand_multiplier,
            climatic_data_year=2025,
            clim_year=2012,
            capa_data_year=capa_data_year,
            p_bat=p_bat,
            capa_bat=capa_bat,
            p_hyd=p_hyd,
            capa_hyd=capa_hyd,
            charge_initiale_stockage=charge_initiale_stockage
        )

        st.success("Réseau prêt. Optimisation en cours...")
        result = network.optimize(solver_name="cbc")
        st.success("Optimisation terminée !")
        
        # --- Affichage des résultats ---
        if result[0] == 'ok':
            st.subheader("Production horaire par source")
            plot_results(network)
            st.pyplot(plt.gcf())
    
            # st.subheader("Bilan énergétique global")
            # plot_energybalance(network)
            # st.pyplot(plt.gcf())
    
            st.subheader("Évolution du stockage")
            plot_evolstorage(network)
            st.pyplot(plt.gcf())
    
            st.subheader("Émissions de CO₂")
            total_co2 = plot_co2overtime(network)
            st.pyplot(plt.gcf())
            st.metric(label="Émissions totales de CO₂", value=f"{total_co2:,.0f} tonnes eq.")
        else:
            st.error("Le solveur n'a pas trouvé de solution satisfaisante. Vous pouvez réduire la charge sur le réseau ou ajouter du stockage.", icon="🚨")

else:
    st.info("Choisis les paramètres et lance la simulation.")
    
    
    
#lancer streamlit : dans cmd !
# conda activate bess
# streamlit run app.py


# bugs à régler : ne fonctionne pas quand on change l'année du scénario ...





