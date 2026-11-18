"""Eligibility is a documented filter, not a score or nationality assumption."""
def classify_candidate(name, evidence):
    name=evidence.get('aliases',{}).get(name,name)
    record=next((p for p in evidence['players'] if p['name'].casefold()==name.casefold()),None)
    entry=next((p for p in evidence.get('confirmed_auction_entries',[]) if p['name'].casefold()==name.casefold() and p.get('source') and p.get('registration_confirmed') is True and p.get('availability_confirmed') is True),None)
    status=record['status'] if record else 'unverified'
    # Retained players cannot be promoted merely by adding a registration record.
    if status in ['retained_rr','retained_elsewhere','reported_retained','unavailable_or_retired','conflicting_report']:
        return {'status':status,'auction_actionable':False,'record':record}
    if entry:
        return {'status':'verified_auction_candidate','auction_actionable':True,'record':entry}
    return {'status':status,'auction_actionable':False,'record':record}


def verified_recruitment_pool(players,evidence):
    return [p for p in players if classify_candidate(p['name'],evidence)['auction_actionable']]
