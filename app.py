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
from main import *
st.set_page_config(page_title="Simulation mix électrique", layout="wide")

# Initialisation de l'historique
if 'historique_simulations' not in st.session_state:
    st.session_state.historique_simulations = []
    
st.title("⚡ Simulation de réseau électrique - France")

# st.markdown{"Bienvenue sur ce simulateur du réseau électrique français. Le programme va chercher à construire le mix électrique optimal pour la période souhaitée, en prenant en compte des contraintes économiques et écologiques pour répondre"}
st.markdown("""### Introduction
Ce document présente les résultats d’une simulation du réseau électrique français, visant à évaluer l’impact du stockage sur les émissions de CO₂.

### Données initiales
Les données proviennent d’ENTSO-E (ERAA 2024), [disponible ici](https://www.entsoe.eu/eraa/2024/downloads/), et incluent :
- Les capacités de production et de stockage prévues pour 2025, 2028, 2030 et 2033.
- La courbe de charge horaire de la France.
- Les facteurs de capacité horaires du solaire, de l’éolien onshore et offshore.

### PyPSA
PyPSA (Python for Power System Analysis) est une librairie permettant la modélisation et l’optimisation de réseaux électriques, incluant générateurs pilotables et sources variables. Elle est adaptée aux simulations de grande échelle.  
Documentation : https://docs.pypsa.org/latest/

### Paramètres
Plusieurs paramètres vous sont accessibles, notamment la quantité de stockage (batterie et hydraulique) présente sur le réseau. N'hésitez pas à expérimenter !""")

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
p_bat = st.sidebar.slider("Puissance batteries (MW)", 1, 2000, 470, 100)
capa_bat = st.sidebar.slider("Capacité batteries (MWh)", 1, 20000, 940, 200)
p_hyd = st.sidebar.slider("Puissance hydro (MW)", 1, 4000, 3800, 500)
capa_hyd = st.sidebar.slider("Capacité hydro (MWh)", 1, 200000, 100000, 5000)



scenario = return_scenario(capa_data_year)
st.subheader(f"Aperçu du scénario choisi : ERAA {capa_data_year}")
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
        result = network.optimize(solver_name="cbc", assign_all_duals=True)
        st.success("Optimisation terminée !")
        
        # --- Affichage des résultats ---
        if result[0] == 'ok':
            
            
            st.plotly_chart(plot_results_plotly(network))
    
            # st.subheader("Bilan énergétique global")
            # plot_energybalance(network)
            # st.pyplot(plt.gcf())
    
            
            st.plotly_chart(plot_evolstorage_plotly(network), width='stretch')
             st.plotly_chart(plot_comparatifco2energy(network),width='stretch')
            
            fig, total_co2 = plot_co2overtime_plotly(network)
            st.plotly_chart(fig, width='stretch')
            st.metric(label="Émissions totales de CO₂", value=f"{total_co2:,.0f} tonnes eq.")
        # --- ENREGISTREMENT DANS L'HISTORIQUE ---
            # On crée un dictionnaire avec les paramètres d'entrée et les résultats clés
            simulation_record = {
                "ID": len(st.session_state.historique_simulations) + 1,
                "Mois": widget_debut,
                "Durée (j)": time_horizon_in_hours/24,
                "Année Scénario": capa_data_year,
                "Demande (x)": demand_multiplier,
                "P Batt (MW)": p_bat,
                "Capa Batt (MWh)": capa_bat,
                "P Hydro (MW)": p_hyd,
                "CO₂ Total (t)": round(total_co2, 2)
            }
            st.session_state.historique_simulations.append(simulation_record)
            
            # --- SECTION TELECHARGEMENT (PERSISTANCE LOCALE) ---
            st.subheader("📥 Téléchargement des données")
            
            # Exemple : Téléchargement des séries temporelles des générateurs
            # On suppose que network.generators_t.p contient la production
            try:
                df_export = network.generators_t.p.copy()
                csv = df_export.to_csv(index=True).encode('utf-8')
                
                st.download_button(
                    label="Télécharger les résultats (CSV)",
                    data=csv,
                    file_name=f'resultats_simulation_{datetime.datetime.now().strftime("%Y%m%d_%H%M")}.csv',
                    mime='text/csv',
                )
            except Exception as e:
                st.warning(f"Préparation du téléchargement impossible : {e}")

        else:
            st.error("Le solveur n'a pas trouvé de solution satisfaisante. Vous pouvez réduire la charge sur le réseau ou ajouter du stockage.", icon="🚨")

else:
    st.info("Choisis les paramètres et lance la simulation.")

if st.session_state.historique_simulations:
    st.divider()
    st.header("📚 Historique et comparaison des scénarios")
    st.write("Ce tableau enregistre vos essais tant que la page reste ouverte.")
    
    # Conversion en DataFrame pour affichage
    df_hist = pd.DataFrame(st.session_state.historique_simulations)
    st.dataframe(df_hist,width='stretch', hide_index=True)
    
    # Bouton pour effacer l'historique
    if st.button("Effacer l'historique"):
        st.session_state.historique_simulations = []
        st.rerun() # Rafraîchit l'app pour mettre à jour l'affichage

        
    
    
#lancer streamlit : dans cmd !
# conda activate bess
# streamlit run app.py


# bugs à régler : ne fonctionne pas quand on change l'année du scénario ...











