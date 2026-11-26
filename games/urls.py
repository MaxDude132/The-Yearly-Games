from django.urls import path

from games import phone_views, tv_views, views

urlpatterns = [
    path("", views.index, name="index"),
    path("roster/", views.roster, name="roster"),
    path("round/next/", views.next_round, name="next_round"),
    path("decision/", views.decision, name="decision"),
    path("quit/", views.quit_game, name="quit"),
    path("undo/", views.undo_last, name="undo"),
    path("skip/", views.skip_to_the_end, name="skip"),
    path("tributes/<int:position>/present/", views.set_present, name="present"),
    path("victors/<int:position>/present/", views.set_victor_present, name="victor_present"),
    path("state/", views.state, name="state"),
    # Players on their phones (the QR code)
    path("play/<str:code>/", phone_views.play, name="play"),
    path("play/<str:code>/join/", phone_views.join, name="play_join"),
    path("play/<str:code>/leave/", phone_views.leave, name="play_leave"),
    path("play/<str:code>/decision/", phone_views.decision, name="play_decision"),
    path("play/<str:code>/bet/", phone_views.bet, name="play_bet"),
    path("play/<str:code>/state/", phone_views.state, name="play_state"),
    # The big screen: the story for the whole room, nothing to press
    path("tv/<str:code>/", tv_views.tv, name="tv"),
]
