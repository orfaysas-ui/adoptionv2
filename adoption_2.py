import pandas as pd
import utils
import datetime
import re

def get_hotel_code(eq, tickets):
    eq = eq.copy()
    tickets = tickets.copy()
    #GET HOTEL CODE
    #get mask
    mask = (
        eq["hotelCode"].str.match(
        r"^h(?=.*\d)[a-z0-9]{4}$",
        flags=re.IGNORECASE,
        na=False) 
    )&(~ eq.hotelCode.isna())&(eq.hotelCode != 'HXXXX')
    #get hotel codes from transcript
    eq["hotel_code_transcript"] = eq["transcript"].str.extract(
        r"\b(h(?=[a-z0-9]*\d)[a-z0-9]{4})\b",
        flags=re.IGNORECASE,
        expand=False
    )
    #get hotel codes from tid
    hotel_codes_tid = eq[mask].groupby('customerHandle').agg(
         hotel_code_tid = ('hotelCode','first')
        ).reset_index().rename(columns={'hotelCode':'hotel_code_tid'})
    eq=eq.merge(hotel_codes_tid, how='left', on = 'customerHandle')
    #get final hotel code
    eq.loc[mask,'hotel_code'] = eq.hotelCode
    eq.loc[~mask,'hotel_code'] = eq.hotel_code_transcript.fillna(eq.hotel_code_tid)
    eq['hotel_code']=eq.hotel_code.str.upper()
    hc_conv = eq[['id','hotel_code']]
    tickets['hotel_code']="H" + tickets["Compte"].str.extract(r"^(.{4})", expand=False)
    hc_ticket = tickets[['Numéro','hotel_code']]
    return (hc_conv, hc_ticket)

def get_clean_dates(e,t,h,min,max):
    t = t.copy()
    h = h.copy()
    #get proper date
    t['date']=pd.to_datetime(t['Créé le'])

    dates = utils.clean_dates(e)
    h['launch_date']=pd.to_datetime(h['Launch date'],dayfirst = True)

    #nb days since launch
    h['max_date']=pd.to_datetime(max)
    h['min_date']=pd.to_datetime(min)
    h['nb_days_since_launch']=(h.max_date-h.launch_date).dt.days
    h['nb_days_selected_window']=(h.max_date-h.min_date).dt.days
    h['nb_weeks_since_launch']=h.nb_days_since_launch//7
    h['nb_weeks_selected_window']=h.nb_days_selected_window//7
    hpw = h.copy()
    hpw["nb_weeks_since_launch"] = (
        hpw["nb_weeks_since_launch"]
        .fillna(0)
        .astype(int)
    )
    h_pw = (
    hpw.assign(week_nb_since_launch=hpw["nb_weeks_since_launch"].apply(lambda x: range(x + 1)))
        .explode("week_nb_since_launch")
        .reset_index(drop=True)
    )
    dt_conv = dates[['id','date']]
    dt_tickets= t[['Numéro','date']]
    return(dt_conv,dt_tickets,h,h_pw)

def remove_blank_csat (eq):
    #REMOVE BLANK CONV AND SURVEY
    transcript = utils.get_transcript(eq)
    questions = utils.get_questions(transcript)
    cgm = utils.conv_gen_metrics(questions)
    #enlever les sans questions et les csat
    tab = eq.merge(cgm, how='left',on='id')
    tab = tab[
        (tab.assignee!='csat-survey')
        &
        (tab.queue!='CSAT Survey')
        &
        (tab.nb_questions>0)]
    return tab


def adoption_analytics (eq,tickets,hotels,min,max):
    # Extraction automatique des tickets Butler depuis les transcripts
    tickets_cid = utils.get_tickets_from_conversations(eq)
    clean_hc = get_hotel_code(eq,tickets)
    clean_dates = get_clean_dates(eq,tickets,hotels,min,max)
    eq = eq.merge(clean_hc[0],how='left', on = 'id')
    eq = eq.merge(clean_dates[0], how='left', on = 'id')
    tab = remove_blank_csat(eq)
    tickets = tickets.merge(clean_hc[1],how='left', on = 'Numéro')
    tickets = tickets.merge(clean_dates[1], how='left', on = 'Numéro')
    hotels = clean_dates[2]
    hotelspw = clean_dates[3]
    hotels['hotel_code']=hotels['Hotel code']
    hotelspw['hotel_code']=hotelspw['Hotel code']
    last_date_measured = tab.date.max()
    last_day_ticket = tickets['date'].max()
    tickets= tickets.merge(hotels[['hotel_code','launch_date']], how='left', on = 'hotel_code')

    tickets['day_nb_since_launch']=(pd.to_datetime(tickets.date)-pd.to_datetime(tickets['launch_date'])).dt.days
    tickets['week_nb_since_launch']= tickets['day_nb_since_launch']//7

    tickets_since_launch = tickets[
        (tickets.date.dt.date<=max)
        &
        (tickets.date.dt.date>= pd.to_datetime(tickets.launch_date).dt.date)
        ]
    tickets_selected_window = tickets[
        (tickets.date.dt.date<=max)
        &(tickets.date.dt.date>=min)
        ]
    
    tab["date"] = pd.to_datetime(tab["date"], errors="coerce").dt.tz_localize(None)
    last_day_ticket = pd.to_datetime(last_day_ticket).tz_localize(None)

    tab=tab.merge(hotels[['hotel_code','launch_date']], how='left', on = 'hotel_code')

    tab['day_nb_since_launch']=(pd.to_datetime(tab.date)-pd.to_datetime(tab.launch_date)).dt.days
    tab['week_nb_since_launch']= tab['day_nb_since_launch']//7

    conv_since_launch = tab[(tab["date"] <= pd.to_datetime(max))&(tab['date']>=pd.to_datetime(tab.launch_date))]
    conv_selected_window = tab[(tab["date"] <= pd.to_datetime(max))&(tab['date']>=pd.to_datetime(min))&(tab['date']>=pd.to_datetime(tab.launch_date))]


    #group by conv
    hconv_since_launch = conv_since_launch.groupby('hotel_code').agg(
        nb_conv_since_launch = ('id','nunique'),
        nb_users_since_launch = ('customerHandle','nunique')
    ).reset_index()
    hconv_selected_window = conv_selected_window.groupby('hotel_code').agg(
        nb_conv_selected_window = ('id','nunique'),
        nb_users_selected_window = ('customerHandle','nunique')
    ).reset_index()
    hlastconv = conv_since_launch.groupby('hotel_code').date.max().reset_index().rename(columns={'date':'last_conv_date'})

    #group by conv / week
    hconv_pw_since_launch = conv_since_launch.groupby(['hotel_code','week_nb_since_launch']).agg(
        nb_conv_pw = ('id','nunique'),
        nb_users_pw = ('customerHandle','nunique')
    ).reset_index()

    #groupby ticket
    tickets_since_launch['through_butler']=tickets_since_launch['Numéro'].isin(tickets_cid['Numéro'])
    tickets_selected_window['through_butler']=tickets_selected_window['Numéro'].isin(tickets_cid['Numéro'])

    nb_tickets_since_launch = tickets_since_launch.groupby('hotel_code')['Numéro'].nunique().reset_index().rename(columns={'Numéro':'nb_tickets_since_launch'})
    nb_tickets_selected_window = tickets_selected_window.groupby('hotel_code')['Numéro'].nunique().reset_index().rename(columns={'Numéro':'nb_tickets_selected_window'})

    nb_tickets_butler_since_launch = tickets_since_launch[tickets_since_launch.through_butler==True].groupby('hotel_code')['Numéro'].nunique().reset_index().rename(columns={'Numéro':'nb_tickets_butler_since_launch'})
    nb_tickets_butler_selected_window = tickets_selected_window[tickets_selected_window.through_butler==True].groupby('hotel_code')['Numéro'].nunique().reset_index().rename(columns={'Numéro':'nb_tickets_butler_selected_window'})

    #groupby ticket/week
    nb_tickets_pw_since_launch = tickets_since_launch.groupby(['hotel_code','week_nb_since_launch'])['Numéro'].nunique().reset_index().rename(columns={'Numéro':'nb_tickets_pw'})
    nb_tickets_butler_pw_since_launch = tickets_since_launch[tickets_since_launch.through_butler==True].groupby(['hotel_code','week_nb_since_launch'])['Numéro'].nunique().reset_index().rename(columns={'Numéro':'nb_tickets_butler_pw'})

    #merges adoption
    hotel_adoption = hotels.merge(nb_tickets_since_launch, how='left', on='hotel_code')
    hotel_adoption = hotel_adoption.merge(nb_tickets_selected_window, how='left', on='hotel_code')
    hotel_adoption = hotel_adoption.merge(nb_tickets_butler_since_launch, how='left', on='hotel_code')
    hotel_adoption = hotel_adoption.merge(nb_tickets_butler_selected_window, how='left', on='hotel_code')
    hotel_adoption = hotel_adoption.merge(hconv_since_launch, how='left', on = 'hotel_code')
    hotel_adoption = hotel_adoption.merge(hconv_selected_window, how='left', on = 'hotel_code')
    hotel_adoption = hotel_adoption.merge(hlastconv, how='left', on = 'hotel_code')

    #merges adoption pw
    hotel_adoption_pw = hotelspw.merge(nb_tickets_pw_since_launch, how='left', on=['hotel_code','week_nb_since_launch'])
    hotel_adoption_pw = hotel_adoption_pw.merge(nb_tickets_butler_pw_since_launch, how='left', on=['hotel_code','week_nb_since_launch'])
    hotel_adoption_pw = hotel_adoption_pw.merge(hconv_pw_since_launch, how='left', on = ['hotel_code','week_nb_since_launch'])


    #new metrics adoption
    hotel_adoption['nb_conv_per_week_since_launch']=hotel_adoption.nb_conv_since_launch.fillna(0)/hotel_adoption.nb_weeks_since_launch
    hotel_adoption['nb_conv_per_user_since_launch']=hotel_adoption.nb_conv_since_launch.fillna(0)/hotel_adoption.nb_users_since_launch
    hotel_adoption['nb_conv_per_week_selected_window']=hotel_adoption.nb_conv_selected_window.fillna(0)/hotel_adoption.nb_weeks_selected_window
    hotel_adoption['nb_conv_per_user_selected_window']=hotel_adoption.nb_conv_selected_window.fillna(0)/hotel_adoption.nb_users_selected_window
    hotel_adoption['tot_nb_demands_since_launch']= hotel_adoption.nb_conv_since_launch.fillna(0) + hotel_adoption.nb_tickets_since_launch.fillna(0) - hotel_adoption.nb_tickets_butler_since_launch.fillna(0)
    hotel_adoption['tot_nb_demands_selected_window']= hotel_adoption.nb_conv_selected_window.fillna(0) + hotel_adoption.nb_tickets_selected_window.fillna(0) - hotel_adoption.nb_tickets_butler_selected_window.fillna(0)
    hotel_adoption['adoption_rate_since_launch']=hotel_adoption.nb_conv_since_launch.fillna(0)/hotel_adoption.tot_nb_demands_since_launch
    hotel_adoption['adoption_rate_selected_window']=hotel_adoption.nb_conv_selected_window.fillna(0)/hotel_adoption.tot_nb_demands_selected_window
    hotel_adoption['nb_days_since_last_conv']=(pd.to_datetime(max)-pd.to_datetime(hotel_adoption.last_conv_date)).dt.days
    hotel_adoption['nb_weeks_since_last_conv']=hotel_adoption.nb_days_since_last_conv//7

    #new metrics adoption pw
    hotel_adoption_pw['tot_nb_demands_pw']= hotel_adoption_pw.nb_conv_pw.fillna(0) + hotel_adoption_pw.nb_tickets_pw.fillna(0) - hotel_adoption_pw.nb_tickets_butler_pw.fillna(0)
    hotel_adoption_pw['adoption_rate_pw']=hotel_adoption_pw.nb_conv_pw.fillna(0)/hotel_adoption_pw.tot_nb_demands_pw
    hotel_adoption_pw['nb_conv_per_user_pw']=hotel_adoption_pw.nb_conv_pw.fillna(0)/hotel_adoption_pw.nb_users_pw



    return (hotel_adoption,hotel_adoption_pw)
