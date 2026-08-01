def test_check_up(client):
    response = client.get("/")
    
    assert response.status_code == 200