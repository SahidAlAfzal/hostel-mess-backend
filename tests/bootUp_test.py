def test_check_up(client):
    response = client.head("/")
    
    assert response.status_code == 200