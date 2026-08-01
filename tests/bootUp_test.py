def test_check_up(client):
    response = client.post("/")
    
    assert response.status_code == 200