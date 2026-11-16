from django.urls import path

from games import views

urlpatterns = [
    path("", views.index, name="index"),
    path("roster/", views.roster, name="roster"),
    path("round/next/", views.next_round, name="next_round"),
    path("decision/", views.decision, name="decision"),
    path("quit/", views.quit_game, name="quit"),
    path("tributes/<int:position>/present/", views.set_present, name="present"),
]
