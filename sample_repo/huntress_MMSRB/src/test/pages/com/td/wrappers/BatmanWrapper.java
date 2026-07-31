package com.td.wrappers;

public class BatmanWrapper {
    private final PropertyValueProvider propertyValueProvider = new PropertyValueProvider();

    public void selectUser(String group, String ssoUser) {
        getPropertyValue(ssoUser);
    }

    public void openApplication(String propertyKey) {
        getPropertyValue(propertyKey);
    }

    public void waitForVisible(String propertyKey) {
        getPropertyValue(propertyKey);
    }

    public void assertNotPresent(String propertyKey) {
        getPropertyValue(propertyKey);
    }

    public void click(String propertyKey) {
        getPropertyValue(propertyKey);
    }

    public void validateCurrentListView(String propertyKey) {
        getPropertyValue(propertyKey);
    }

    public String getPropertyValue(String propertyKey) {
        return propertyValueProvider.getPropertyValue(propertyKey);
    }
}
