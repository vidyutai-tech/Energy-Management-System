import { createContext, useState, useCallback, useMemo } from "react";
import PropTypes from "prop-types";

// Define appliance names
const applianceNames = [
  "LED bulbs",
  "LED Tubes",
  "Celling Fans",
  "Movable Fans",
  "Lamps",
  "Computer/Laptops",
  "Televisions",
  "Audio Outputs",
  "Air Purifiers",
  "Air cooler",
  "Air Conditioners",
  "Iron",
  "Hair Dryer",
  "Vacuum Cleaner",
  "Refrigerator",
  "Blender/ Mixers",
  "Water Purifiers",
  "Electric Kettle",
  "Induction Cooker",
  "Toaster",
  "Microwave Oven",
  "Dish Washer",
  "Washing Machines",
  "Dryers",
  "Water Heater (Geyser)",
  "Room Heater",
  "Water Pump",
];

// Initialize the object with appliance names as keys
const initialObject = applianceNames.reduce((acc, name) => {
  acc[name] = {
    low: { rating: 0, number: 0, hoursUsed: 0, total: 0 },
    medium: { rating: 0, number: 0, hoursUsed: 0, total: 0 },
    high: { rating: 0, number: 0, hoursUsed: 0, total: 0 },
    other: { rating: 0, number: 0, hoursUsed: 0, total: 0 },
  };
  return acc;
}, {});

const EnergyContext = createContext();

export const EnergyProvider = ({ children }) => {
  const [choices, setChoices] = useState({
    energySource: [],
    dieselUse: "",
    energyGoal: "",
  });

  const [applianceNamesEnergyCost, setApplianceNamesEnergyCost] =
    useState(initialObject);
  const [miscellaneousItems, setMiscellaneousItems] = useState([]);
  const [userEmail, setUserEmail] = useState("");

  const handleChoiceChange = (e) => {
    const { name, value, type, checked } = e.target;
    setChoices((prevChoices) => {
      if (type === "checkbox") {
        if (checked) {
          return {
            ...prevChoices,
            [name]: [...(prevChoices[name] || []), value],
          };
        } else {
          return {
            ...prevChoices,
            [name]: prevChoices[name].filter((item) => item !== value),
          };
        }
      } else if (type === "radio") {
        return {
          ...prevChoices,
          [name]: value,
        };
      }
      return prevChoices;
    });
  };

  const calculateTotalEnergyConsumption = useCallback(() => {
    const total = { low: 0, medium: 0, high: 0, other: 0 };

    Object.values(applianceNamesEnergyCost).forEach((appliance) => {
      ["low", "medium", "high", "other"].forEach((category) => {
        total[category] += appliance[category].total;
      });
    });

    miscellaneousItems.forEach((item) => {
      ["low", "medium", "high", "other"].forEach((category) => {
        total[category] += item[category].total;
      });
    });

    return total;
  }, [applianceNamesEnergyCost, miscellaneousItems]);

  const totalEnergyConsumption = useMemo(
    () => calculateTotalEnergyConsumption(),
    [calculateTotalEnergyConsumption],
  );

  const totalEnergyUsage = useMemo(() => {
    return Object.values(totalEnergyConsumption).reduce(
      (acc, curr) => acc + curr,
      0,
    );
  }, [totalEnergyConsumption]);

  return (
    <EnergyContext.Provider
      value={{
        choices,
        setChoices,
        handleChoiceChange,
        applianceNamesEnergyCost,
        setApplianceNamesEnergyCost,
        miscellaneousItems,
        setMiscellaneousItems,
        totalEnergyConsumption,
        totalEnergyUsage,
        userEmail,
        setUserEmail,
      }}
    >
      {children}
    </EnergyContext.Provider>
  );
};

EnergyProvider.propTypes = {
  children: PropTypes.node.isRequired,
};

export default EnergyContext;
