# -*- coding: utf-8 -*-
"""
Created on Mon Nov  3 10:40:44 2025

@author: noego
"""
import streamlit as st
import pypsa
import pandas as pd
from dataclasses import dataclass
from datetime import timedelta
import matplotlib.pyplot as plt
pd.set_option('future.no_silent_downcasting', True)

def prep_network(time_horizon_in_hours,date_debut,demand_multiplier,climatic_data_year,clim_year,capa_data_year,p_bat,capa_bat,p_hyd,capa_hyd,charge_initiale_stockage):


    
    full_demand = pd.read_csv("./data/Demand_TimeSeries/demand_"+str(climatic_data_year)+"_france.csv", sep=";", index_col=1, parse_dates=True).groupby(
        pd.Grouper(key="climatic_year"))

    
    demand = full_demand.get_group(clim_year)

    

    snapshots=demand.index[date_debut:(date_debut+time_horizon_in_hours)]
    network = pypsa.Network(snapshots=snapshots)
    
    # On crée un seul bus "France"
    network.add("Carrier", "AC")
    network.add("Bus", "FR", x=2.2, y=46.2,carrier="AC")
    #ajout_generation():
    #Lecture du fichier des capacitées estimées

    eraa_capa = pd.read_csv("./data/ERAA_National_Estimates_capacities_"+str(capa_data_year)+"_france.csv", sep=';')
    eraa_storage = eraa_capa[eraa_capa["energy_capacity (MWh)"].notna()]
    eraa_gen = eraa_capa[eraa_capa["energy_capacity (MWh)"].isnull()]
    eraa_gen = eraa_gen[eraa_gen["power_capacity (MW)"] > 0]


    fuel_sources = prep_generators(climatic_data_year,clim_year,snapshots)
    
    
    for fuel_source in fuel_sources.values():
        network.add("Carrier", **fuel_source.carrier_characteristics())


        
        
    # Ajout des plants de notre fichier un par un
    print("Ajout des générateurs ...")
    for _, plant in eraa_gen.iterrows():
        
        network.add(
            "Generator",
            name=plant["name"],
            bus="FR",
            carrier=plant["name"],    
            p_nom=plant["power_capacity (MW)"],
            p_min_pu=fuel_sources[plant["name"]].p_min_pu,
            p_max_pu=fuel_sources[plant["name"]].p_max_pu,
            marginal_cost=fuel_sources[plant["name"]].marginal_cost,            
            efficiency=fuel_sources[plant["name"]].efficiency,
            **(fuel_sources[plant["name"]].generator_characteristics()) 
        )
        

    print('Ajout des unités de stockage ...')
        
    print('Ajout des unités de stockage ...')
        
    network.add('Carrier',
                name='Stockage-hydro',
                co2_emissions=0)
    network.add("StorageUnit",
                name='Hydro - pompage',
                bus="FR",
                carrier="Stockage-hydro",
                p_nom=p_hyd,
                max_hours=capa_hyd/p_hyd,
                state_of_charge_initial = capa_hyd*charge_initiale_stockage,
                p_nom_extendable=False,
                p_min_pu = -1.0)
    network.add('Carrier',
                name='Stockage-bat',
                co2_emissions=0.0256)
    network.add("StorageUnit",
                name='Batteries',
                bus="FR",
                carrier="Stockage-bat",
                p_nom=p_bat,
                max_hours=capa_bat/p_bat,
                state_of_charge_initial = capa_bat*charge_initiale_stockage,
                p_nom_extendable=False,
                p_min_pu = -1.0)





    network.add("Load",
                name= "France-load",
                bus= "FR",
                carrier= "AC",
                p_set= pd.Series(demand[date_debut:(date_debut+time_horizon_in_hours)]["value"].values*demand_multiplier,index=snapshots),)
    
    print('Network prêt.')  
    print(network.components)
    return network




def plot_results(network):
    COLOR_MAP = {
    "Gas ": "black",
    "Hydro - Run of River (Turbine)": "royalblue",
    "Nuclear": "orange",
    "Oil": "black",
    "Others renewable" : "forestgreen",
    "Solar (Photovoltaic)" : "gold",
    "Wind Offshore": "skyblue",
    "Wind Onshore": "navy",
    "Stockage-bat (décharge)" : "crimson",
    'Stockage-bat (charge)':'crimson',
    "Stockage-hydro (décharge)": "mediumorchid",
    "Stockage-hydro (charge)": "mediumorchid"
    }
    
    gen_prod = network.generators_t.p
    gen_carrier = network.generators.carrier
    prod_by_gen = gen_prod.groupby(gen_carrier, axis=1).sum()

    # --- Stockage ---
    storage_prod = network.storage_units_t.p
    storage_carrier = network.storage_units.carrier
    prod_by_storage = storage_prod.groupby(storage_carrier, axis=1).sum()


    # --- Tracer ---

    all_prod = prod_by_gen
    all_neg = pd.DataFrame(index=prod_by_gen.index)
    # Stockage : séparer charge (négatif) et décharge (positif)
    for col in prod_by_storage.columns:
        pos = prod_by_storage[col].clip(lower=0)
        neg = prod_by_storage[col].clip(upper=0)
        # if pos.sum() > 0:
        all_prod = pd.concat([all_prod, pd.DataFrame({f"{col} (décharge)":pos.values},index=prod_by_gen.index)], axis=1)
        # if neg.sum() < 0:
        all_neg = pd.concat([all_neg, pd.DataFrame({f"{col} (charge)":neg.values},index=prod_by_gen.index)], axis=1)


    # colors_prod = plt.cm.tab20.colors[:len(all_prod.columns)]
    # colors_neg = plt.cm.tab20.colors[len(all_prod.columns):len(all_prod.columns)+len(all_neg.columns)]
    colors_prod = [COLOR_MAP.get(col, "grey") for col in all_prod.columns]
    colors_neg  = [COLOR_MAP.get(col, "lightgrey") for col in all_neg.columns]



    fig, ax = plt.subplots(figsize=(30,10), facecolor="#F0F0F0")    
    ax.stackplot(all_neg.index, all_neg.T.values, labels=all_neg.columns, alpha=0.7,colors=colors_neg)
    ax.stackplot(all_prod.index, all_prod.T.values, labels=all_prod.columns, alpha=0.7,colors=colors_prod)
    
    # courbe de demande
    # on adapte la courbe de demande pour qu'elle prenne en compte l'énergie stockée
    ax.plot(network.loads_t['p_set'].index, network.loads_t['p_set'].sum(axis=1)-all_neg.sum(axis=1), color='black', lw=1, label='Demande')
    ax.autoscale(enable=False)
    ax.set_xlabel("Temps")
    ax.set_ylabel("Puissance (MW)")
    ax.set_title("Production et charge horaire par source d'énergie")
    # ax.set_ylim(bottom=min(prod_by_storage.min().min(), 0) * 1.5, top=demand["value"].max()*1.2)
    ax.grid(which="major", color="grey", linestyle="--", linewidth=0.5)
    ax.legend(loc="upper right", fontsize=8)



def plot_energybalance(network):
    colors= plt.cm.tab20.colors[:len(network.statistics.energy_balance().loc[:, :, "AC"].groupby("carrier").sum())]
    fig, ax = plt.subplots()
    network.statistics.energy_balance().loc[:, :, "AC"].groupby(
        "carrier"
        ).sum().to_frame().T.plot.bar(stacked=True,
                                      ax=ax,
                                      title="Energy Balance",
                                      color=colors)

    ax.legend(bbox_to_anchor=(1, 0), loc="lower left", title=None, ncol=1)


def plot_scenarios(annee):
    eraa_capa = pd.read_csv("./data/ERAA_National_Estimates_capacities_"+str(annee)+"_france.csv", sep=';')
    eraa_gen = eraa_capa[eraa_capa["energy_capacity (MWh)"].isnull()]
    eraa_gen = eraa_gen[eraa_gen["power_capacity (MW)"] > 0]
    plt.bar(eraa_gen['name'], eraa_gen['power_capacity (MW)'])
    plt.title('Energy Balance')
    plt.ylabel('Power Capacity (MW)')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.show()
    
def return_scenario(annee):
    eraa_capa = pd.read_csv("./data/ERAA_National_Estimates_capacities_"+str(annee)+"_france.csv", sep=';')
    eraa_gen = eraa_capa[eraa_capa["energy_capacity (MWh)"].isnull()]
    eraa_gen = eraa_gen[eraa_gen["power_capacity (MW)"] > 0].drop('energy_capacity (MWh)',axis=1)
    return eraa_gen  

def plot_evolstorage(network):
    SOC = network.storage_units_t.state_of_charge.copy() 
    max_e_hydro = network.storage_units.p_nom["Hydro - pompage"] * network.storage_units.max_hours["Hydro - pompage"]
    max_e_bat = network.storage_units.p_nom["Batteries"] * network.storage_units.max_hours["Batteries"]
    if max_e_hydro > 0:
        SOC['Hydro - pompage'] = (SOC['Hydro - pompage'] / max_e_hydro) * 100
    if max_e_bat > 0:
        SOC['Batteries'] = (SOC['Batteries'] / max_e_bat) * 100
        
    fig, ax = plt.subplots(figsize=(30,10), facecolor="#F0F0F0") 
    ax.plot(SOC.index, SOC.values,label=SOC.columns)
    ax.set_xlabel("Temps")
    ax.set_ylabel("State of charge (%)")
    ax.set_title("Evolution du taux de charge de la batterie")
    ax.grid(which="major", color="grey", linestyle="--", linewidth=0.5)
    ax.legend(loc="upper right", fontsize=8)


# Attention, pas de temps de 1h pour que les calculs soient valides
#Calcul : émission co2 en tonnes/MWh * MWh produits par heure
# on fait la somme de tout ça
def plot_co2overtime(network):
    co2_list = network.generators.carrier.map(network.carriers.co2_emissions)
    co2_overtime = (network.generators_t.p*co2_list).sum(axis=1)
    fig, ax = plt.subplots(figsize=(30,10), facecolor="#F0F0F0") 
    ax.bar(co2_overtime.index, co2_overtime.values,width=timedelta(hours=1))
    ax.set_xlabel("Temps")
    ax.set_ylabel("Tonnes Co2 Eq")
    ax.set_title("Emissions de C02 (Tonnes Co2 Eq.)")
    ax.grid(which="major", color="grey", linestyle="--", linewidth=0.5)
    ax.legend(loc="upper right", fontsize=8)
    
    # retourne émissions totales en tonnes de co2
    return co2_overtime.sum()



@dataclass
class FuelSources:
    name: str
    co2_emissions: float
    committable: bool
    min_up_time: float
    min_down_time: float
    energy_density_per_ton: float  # in MWh / ton
    cost_per_ton: float
    efficiency: float
    p_min_pu: float = 0
    p_max_pu:float = 1
    ramp_limit_up: float = None        
    ramp_limit_down: float = None
    primary_cost: float = None  # € / MWh (multiply this by the efficiency of your power plant to get the marginal cost)
    marginal_cost: float = None
        
    def __post_init__(self):
        if self.energy_density_per_ton != 0:
            self.primary_cost = self.cost_per_ton / self.energy_density_per_ton
        else:
            self.primary_cost = 0
        self.marginal_cost = self.primary_cost*self.efficiency

    def return_as_dict(self, keys):
        return {key: self.__dict__[key] for key in keys}

    def carrier_characteristics(self):
        return self.return_as_dict(["name", "co2_emissions"])

    def generator_characteristics(self):
        return self.return_as_dict(["committable", "min_up_time", "min_down_time","ramp_limit_up", "ramp_limit_down"])
  

def prep_generators(climatic_data_year,clim_year,snapshots):
    
    # facteur de charge de l'eolien on shore
    full_wind_on_shore = pd.read_csv("./data/capa/Wind_Onshore/capa_factor_"+str(climatic_data_year)+"_france.csv", index_col=1, parse_dates=True, sep=";").groupby(
        pd.Grouper(key="climatic_year"))

    # facteur de charge de l'eolien off shore en pologne
    full_wind_off_shore = pd.read_csv("./data/capa/Wind_Offshore/capa_factor_"+str(climatic_data_year)+"_france.csv", index_col=1, parse_dates=True, sep=";").groupby(
        pd.Grouper(key="climatic_year"))

    # facteur de charge du solaire
    PV = pd.read_csv("./data/capa/Solar_PV/capa_factor_"+str(climatic_data_year)+"_france.csv", index_col=1, parse_dates=True, sep=";").groupby(
        pd.Grouper(key="climatic_year"))
    
    wind_on_shore = full_wind_on_shore.get_group(clim_year)
    wind_off_shore = full_wind_off_shore.get_group(clim_year)
    PVprod = PV.get_group(clim_year)
    
    
    fuel_sources = {
        "Nuclear": FuelSources(name="Nuclear",
                               co2_emissions=5e-3,
                               committable=True,
                               min_up_time=1,
                               min_down_time=1,
                               energy_density_per_ton=22394,
                               cost_per_ton=150000.84,
                               efficiency=0.37,
                               ramp_limit_up=0.01,
                               ramp_limit_down=0.01,
                               marginal_cost=50),
        "Oil": FuelSources(name="Oil",
                               co2_emissions=901e-3,
                               committable=True,
                               min_up_time=1,
                               min_down_time=1,
                               energy_density_per_ton=11.63,
                               cost_per_ton=555.78,
                               efficiency=0.4),
        "Gas ": FuelSources(name="Gas ",
                               co2_emissions=512e-3,
                               committable=True,
                               min_up_time=2,
                               min_down_time=2,
                               energy_density_per_ton=14.89,
                               cost_per_ton=134.34,
                               efficiency=0.5),
        "Solar (Photovoltaic)": FuelSources(name="Solar (Photovoltaic)",
                               co2_emissions=30e-3,
                               committable=False,
                               min_up_time=1,
                               min_down_time=1,
                               energy_density_per_ton=0,
                               cost_per_ton=0,
                               efficiency=1,
                               p_min_pu = PVprod["value"].reindex(snapshots, fill_value=0),
                               p_max_pu = PVprod["value"].reindex(snapshots, fill_value=0)),
        "Wind Onshore": FuelSources(name="Wind Onshore",
                               co2_emissions=13e-3,
                               committable=False,
                               min_up_time=1,
                               min_down_time=1,
                               energy_density_per_ton=0,
                               cost_per_ton=0,
                               efficiency=1,
                               p_min_pu = wind_on_shore["value"].reindex(snapshots, fill_value=0),
                               p_max_pu = wind_on_shore["value"].reindex(snapshots, fill_value=0)),
        "Wind Offshore": FuelSources(name="Wind Offshore",
                               co2_emissions=13e-3,
                               committable=False,
                               min_up_time=1,
                               min_down_time=1,
                               energy_density_per_ton=0,
                               cost_per_ton=0,
                               efficiency=1,
                               p_min_pu = wind_off_shore["value"].reindex(snapshots, fill_value=0),
                               p_max_pu = wind_off_shore["value"].reindex(snapshots, fill_value=0)),
        "Hydro - Run of River (Turbine)": FuelSources(name="Hydro - Run of River (Turbine)",
                               co2_emissions=0,
                               committable=True,
                               min_up_time=1,
                               min_down_time=1,
                               energy_density_per_ton=0,
                               cost_per_ton=0,
                               efficiency=1),
        "Others renewable": FuelSources(name="Others renewable",
                               co2_emissions=230e-3,
                               committable=True,
                               min_up_time=1,
                               min_down_time=1,
                               energy_density_per_ton=0,
                               cost_per_ton=0,
                               efficiency=1),
        "Demand Side Response capacity": FuelSources(name="Demand Side Response capacity",
                               co2_emissions=0,
                               committable=True,
                               min_up_time=0,
                               min_down_time=int(len(snapshots)*0.8), #ne pas abuser des bonnes choses
                               energy_density_per_ton=0,
                               cost_per_ton=0,
                               efficiency=1,
                               ramp_limit_up=100,
                               ramp_limit_down=100,
                               marginal_cost=250),
    }
    return fuel_sources





















